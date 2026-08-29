from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from uuid import uuid4
from typing import Any, Protocol

from research_platform.platform.kernel import JsonObject, canonical_bytes, canonical_digest
from research_platform.platform.kernel.errors import describe_exception
from research_platform.platform.kernel.durability.durable_file import (
    atomic_replace_bytes,
    durable_unlink,
    fsync_directory,
)
from research_platform.scope.path.api import is_absolute_target_path

from ..api import (
    MinecraftCheckpointPort,
    MinecraftRconEndpoint,
    MinecraftServerLifecyclePort,
    MinecraftServerSpec,
    MinecraftWorldBranch,
    MinecraftWorldCut,
    MinecraftWorldCutMetadataStorePort,
    MinecraftWorldCutPort,
    MinecraftWorldQuiescence,
    MinecraftWorldQuiescencePort,
)
from .rcon import MinecraftRconConsole
from .world_quiescence import MinecraftSaveQuiescenceProvider


_CUT_SCHEMA = "minecraft-world-cut.v1"
_BRANCH_SCHEMA = "minecraft-world-branch.v1"
_EXCLUDED_DIRECTORIES = frozenset({"logs", "crash-reports"})
_EXCLUDED_FILES = frozenset({"session.lock"})


class MinecraftWorldCutError(RuntimeError):
    """A world-cut or branch operation failed with a stable cause code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"Minecraft world cut failed [{code}]: {message}")
        self.code = code


def _safe_exception_message(exc: BaseException) -> str:
    descriptor = describe_exception(exc)
    return f"{descriptor.error_type}[{descriptor.error_digest[:16]}]"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _local_path(value: str, *, field: str) -> Path:
    path = Path(value).expanduser().resolve(strict=False)
    if not is_absolute_target_path(path):
        raise MinecraftWorldCutError("PATH_NOT_ABSOLUTE", f"{field} is not absolute: {value!r}")
    return path


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_child(path: Path, root: Path, *, field: str) -> Path:
    resolved = path.resolve(strict=False)
    if resolved == root or not _within(resolved, root):
        raise MinecraftWorldCutError(
            "PATH_OUTSIDE_PROVIDER_ROOT",
            f"{field} must be a strict child of {root}: {resolved}",
        )
    return resolved


def _excluded(relative: Path) -> bool:
    return bool(
        _EXCLUDED_FILES.intersection({relative.name})
        or _EXCLUDED_DIRECTORIES.intersection(set(relative.parts))
    )


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in _EXCLUDED_DIRECTORIES or name in _EXCLUDED_FILES
    }


def _validate_source(source: Path, level_name: str) -> None:
    if not source.is_dir():
        raise MinecraftWorldCutError("SOURCE_WORKDIR_MISSING", str(source))
    level = source / level_name
    if not level.is_dir():
        raise MinecraftWorldCutError("SOURCE_LEVEL_MISSING", str(level))
    if not (level / "level.dat").is_file():
        raise MinecraftWorldCutError("SOURCE_LEVEL_DAT_MISSING", str(level / "level.dat"))


def _tree_manifest(root: Path) -> tuple[dict[str, object], ...]:
    files: list[tuple[str, int, Path]] = []

    def _walk_error(exc: OSError) -> None:
        raise MinecraftWorldCutError(
            "WORLD_SCAN_FAILED", f"{root}: {type(exc).__name__}: {exc}"
        ) from exc

    for current, directories, names in os.walk(
        root, topdown=True, followlinks=False, onerror=_walk_error
    ):
        current_path = Path(current)
        directories.sort()
        names.sort()
        for name in tuple(directories):
            child = current_path / name
            relative = child.relative_to(root)
            if _excluded(relative):
                directories.remove(name)
                continue
            mode = child.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise MinecraftWorldCutError("SYMLINK_UNSUPPORTED", str(child))
            if not stat.S_ISDIR(mode):
                raise MinecraftWorldCutError("UNSUPPORTED_FILE_TYPE", str(child))
        for name in names:
            child = current_path / name
            relative = child.relative_to(root)
            if _excluded(relative):
                continue
            info = child.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise MinecraftWorldCutError("SYMLINK_UNSUPPORTED", str(child))
            if not stat.S_ISREG(info.st_mode):
                raise MinecraftWorldCutError("UNSUPPORTED_FILE_TYPE", str(child))
            files.append((relative.as_posix(), info.st_size, child))

    rows = tuple(
        {"path": relative, "size": size, "sha256": _sha256(path)}
        for relative, size, path in sorted(files, key=lambda item: item[0])
    )
    if not rows:
        raise MinecraftWorldCutError("SOURCE_EMPTY", str(root))
    return rows


def _manifest_digest(manifest: tuple[dict[str, object], ...]) -> str:
    return canonical_digest(manifest)


def _metadata_bytes(value: JsonObject) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _file_ref(path: Path) -> str:
    return f"file:{path}"


def _path_from_ref(value: str) -> Path:
    if not value.startswith("file:"):
        raise MinecraftWorldCutError("SNAPSHOT_REF_UNSUPPORTED", value)
    return _local_path(value[5:], field="snapshot_ref")


def _validated_manifest(value: object, *, source: str) -> tuple[dict[str, object], ...]:
    """Decode the content manifest without allowing ambiguous JSON shapes."""

    if not isinstance(value, list):
        raise MinecraftWorldCutError("SNAPSHOT_MANIFEST_SHAPE", source)
    rows: list[dict[str, object]] = []
    paths: set[str] = set()
    for row in value:
        if not isinstance(row, dict):
            raise MinecraftWorldCutError("SNAPSHOT_MANIFEST_ROW", source)
        relative = row.get("path")
        size = row.get("size")
        digest = row.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative.startswith("/")
            or "\\" in relative
            or any(part in {"", ".", ".."} for part in relative.split("/"))
            or relative in paths
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            raise MinecraftWorldCutError("SNAPSHOT_MANIFEST_ROW", source)
        paths.add(relative)
        rows.append({"path": relative, "size": size, "sha256": digest.lower()})
    if not rows:
        raise MinecraftWorldCutError("SNAPSHOT_MANIFEST_EMPTY", source)
    return tuple(rows)


class MinecraftWorldCopier(Protocol):
    def copy(self, source: Path, destination: Path) -> None: ...


class FilesystemMinecraftWorldCopier:
    """Replaceable local copier; the provider owns the copy contract, not speed policy."""

    def copy(self, source: Path, destination: Path) -> None:
        if destination.exists():
            raise MinecraftWorldCutError("DESTINATION_ALREADY_EXISTS", str(destination))
        try:
            shutil.copytree(source, destination, ignore=_copy_ignore)
        except Exception as exc:
            raise MinecraftWorldCutError(
                "WORLD_COPY_FAILED",
                f"{source} -> {destination}: {type(exc).__name__}: {exc}",
            ) from exc


class ReflinkMinecraftWorldCopier:
    """Linux copier with an explicit, observable capability fallback.

    The default remains strict: an unavailable reflink filesystem is an error.
    A caller may inject a fallback copier only when the deployment has
    deliberately declared that capability failure should use another copy
    policy. This prevents an accidental performance downgrade from being
    hidden inside the provider.
    """

    def __init__(
        self,
        *,
        cp_executable: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        platform_name: str | None = None,
        fallback_copier: MinecraftWorldCopier | None = None,
        fallback_reporter: Callable[[str], None] | None = None,
    ) -> None:
        self.cp_executable = cp_executable
        self.runner = runner or subprocess.run
        self.platform_name = platform_name or os.name
        self.fallback_copier = fallback_copier
        self.fallback_reporter = fallback_reporter
        self.fallback_report_failures: list[str] = []

    @staticmethod
    def _remove_volatile(destination: Path) -> None:
        for current, directories, files in os.walk(destination, topdown=True):
            current_path = Path(current)
            for name in tuple(directories):
                if name in _EXCLUDED_DIRECTORIES:
                    shutil.rmtree(current_path / name)
                    directories.remove(name)
            for name in files:
                if name in _EXCLUDED_FILES:
                    (current_path / name).unlink(missing_ok=True)

    def copy(self, source: Path, destination: Path) -> None:
        if destination.exists():
            raise MinecraftWorldCutError("DESTINATION_ALREADY_EXISTS", str(destination))
        if self.platform_name != "posix":
            raise MinecraftWorldCutError(
                "REFLINK_UNSUPPORTED_PLATFORM",
                f"reflink copier requires POSIX target, got {self.platform_name}",
            )
        executable = self.cp_executable or shutil.which("cp")
        if not executable:
            raise MinecraftWorldCutError("REFLINK_TOOL_MISSING", "cp executable is unavailable")
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            executable,
            "-a",
            "--reflink=always",
            "--",
            f"{source}/.",
            str(destination),
        ]
        try:
            result = self.runner(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise MinecraftWorldCutError(
                "REFLINK_COPY_LAUNCH_FAILED",
                f"{type(exc).__name__}: {exc}",
            ) from exc
        if result.returncode != 0:
            detail = str(result.stderr or result.stdout or "<no cp output>").strip()[-2048:]
            lowered = detail.casefold()
            capability_failure = any(
                marker in lowered
                for marker in ("operation not supported", "invalid cross-device link", "reflink")
            )
            if self.fallback_copier is not None and capability_failure:
                if destination.exists():
                    shutil.rmtree(destination)
                try:
                    self.fallback_copier.copy(source, destination)
                except BaseException as exc:
                    raise MinecraftWorldCutError(
                        "REFLINK_FALLBACK_FAILED",
                        f"reflink={detail}; fallback={type(exc).__name__}: {exc}",
                    ) from exc
                if self.fallback_reporter is not None:
                    try:
                        self.fallback_reporter(detail)
                    except BaseException as exc:
                        self.fallback_report_failures.append(
                            f"{type(exc).__name__}: {exc}"
                        )
                return
            raise MinecraftWorldCutError(
                "REFLINK_COPY_FAILED",
                f"returncode={result.returncode}; detail={detail}",
            )
        if not destination.is_dir():
            raise MinecraftWorldCutError(
                "REFLINK_COPY_OUTPUT_MISSING",
                str(destination),
            )
        self._remove_volatile(destination)


class _CallableMetadataStore(MinecraftWorldCutMetadataStorePort):
    def __init__(self, writer: Callable[[Path, bytes], None]) -> None:
        self._writer = writer

    def publish(self, path: str, payload: bytes) -> None:
        self._writer(Path(path), payload)


class FilesystemMinecraftWorldCutMetadataStore(MinecraftWorldCutMetadataStorePort):
    """Default durable metadata adapter for the local world-cut provider."""

    def publish(self, path: str, payload: bytes) -> None:
        atomic_replace_bytes(Path(path), payload)


class FilesystemMinecraftWorldCutProvider(MinecraftWorldCutPort):
    """Crash-aware local implementation of the MC world-cut/branch seam."""

    def __init__(
        self,
        *,
        quiescence: MinecraftWorldQuiescencePort,
        snapshot_root: str | Path,
        branch_root: str | Path,
        copier: MinecraftWorldCopier | None = None,
        metadata_writer: Callable[[Path, bytes], None] | None = None,
        metadata_store: MinecraftWorldCutMetadataStorePort | None = None,
    ) -> None:
        self.quiescence = quiescence
        self.snapshot_root = _local_path(str(snapshot_root), field="snapshot_root")
        self.branch_root = _local_path(str(branch_root), field="branch_root")
        if self.snapshot_root == self.branch_root or _within(self.snapshot_root, self.branch_root) or _within(self.branch_root, self.snapshot_root):
            raise ValueError("snapshot_root and branch_root must be disjoint")
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        self.branch_root.mkdir(parents=True, exist_ok=True)
        self.copier = copier or FilesystemMinecraftWorldCopier()
        if metadata_writer is not None and metadata_store is not None:
            raise ValueError("provide metadata_store or metadata_writer, not both")
        if metadata_store is not None:
            self.metadata_store = metadata_store
        elif metadata_writer is not None:
            self.metadata_store = _CallableMetadataStore(metadata_writer)
        else:
            self.metadata_store = FilesystemMinecraftWorldCutMetadataStore()

    @staticmethod
    def _identity_path(root: Path, identity: str) -> Path:
        return root / hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def _cut_dir(self, cut_id: str) -> Path:
        return self._identity_path(self.snapshot_root / "cuts", cut_id)

    def _publish_metadata(self, path: Path, value: JsonObject) -> None:
        self.metadata_store.publish(str(path), _metadata_bytes(value))

    def _read_cut(self, cut: MinecraftWorldCut) -> tuple[Path, Mapping[str, Any]]:
        payload = _path_from_ref(cut.snapshot_ref)
        manifest_path = _path_from_ref(cut.manifest_ref)
        if not _within(payload, self.snapshot_root) or not _within(manifest_path, self.snapshot_root):
            raise MinecraftWorldCutError("SNAPSHOT_REF_OUTSIDE_PROVIDER_ROOT", cut.cut_id)
        if not payload.is_dir() or not manifest_path.is_file():
            raise MinecraftWorldCutError("SNAPSHOT_MISSING", cut.cut_id)
        try:
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MinecraftWorldCutError("SNAPSHOT_MANIFEST_INVALID", _safe_exception_message(exc)) from exc
        if not isinstance(document, dict) or document.get("schema_version") != _CUT_SCHEMA:
            raise MinecraftWorldCutError("SNAPSHOT_MANIFEST_SCHEMA", cut.cut_id)
        expected = _validated_manifest(document.get("files"), source=str(manifest_path))
        if _manifest_digest(expected) != cut.manifest_digest or document.get("manifest_digest") != cut.manifest_digest:
            raise MinecraftWorldCutError("SNAPSHOT_MANIFEST_DIGEST", cut.cut_id)
        if (
            document.get("cut_id") != cut.cut_id
            or document.get("level_name") != cut.level_name
            or document.get("server_contract_digest") != cut.server_contract_digest
            or document.get("process_identity_digest") != cut.process_identity_digest
            or document.get("save_evidence_ref") != cut.save_evidence_ref
        ):
            raise MinecraftWorldCutError("SNAPSHOT_IDENTITY_MISMATCH", cut.cut_id)
        actual = _tree_manifest(payload)
        if actual != expected:
            raise MinecraftWorldCutError("SNAPSHOT_CONTENT_MISMATCH", cut.cut_id)
        return payload, document

    def capture(
        self,
        *,
        session_id: str,
        context: Any,
    ) -> MinecraftWorldCut:
        quiescence = self.quiescence.save_and_quiesce(session_id=session_id, context=context)
        capture_error: BaseException | None = None
        cut: MinecraftWorldCut | None = None
        try:
            source = _local_path(quiescence.source_workdir, field="source_workdir")
            if _within(source, self.snapshot_root) or _within(source, self.branch_root):
                raise MinecraftWorldCutError("SOURCE_ROOT_OVERLAP", str(source))
            _validate_source(source, quiescence.level_name)
            manifest = _tree_manifest(source)
            digest = _manifest_digest(manifest)
            cut_id = "minecraft-cut:" + canonical_digest(
                {
                    "quiescence_digest": quiescence.digest(),
                    "manifest_digest": digest,
                }
            )
            cut_dir = self._cut_dir(cut_id)
            payload = cut_dir / "payload"
            manifest_path = cut_dir / "manifest.json"
            if cut_dir.exists():
                cut = MinecraftWorldCut(
                    cut_id,
                    _file_ref(payload),
                    _file_ref(manifest_path),
                    quiescence.level_name,
                    quiescence.server_contract_digest,
                    quiescence.process_identity_digest,
                    digest,
                    quiescence.save_evidence_ref,
                )
                self._read_cut(cut)
            else:
                cut_parent = cut_dir.parent
                cut_parent.mkdir(parents=True, exist_ok=True)
                temporary = Path(tempfile.mkdtemp(prefix=".minecraft-cut-", dir=str(cut_parent)))
                try:
                    temporary_payload = temporary / "payload"
                    self.copier.copy(source, temporary_payload)
                    if _tree_manifest(temporary_payload) != manifest:
                        raise MinecraftWorldCutError("CUT_COPY_DIGEST_MISMATCH", cut_id)
                    self._publish_metadata(
                        temporary / "manifest.json",
                        {
                            "schema_version": _CUT_SCHEMA,
                            "cut_id": cut_id,
                            "level_name": quiescence.level_name,
                            "server_contract_digest": quiescence.server_contract_digest,
                            "process_identity_digest": quiescence.process_identity_digest,
                            "quiescence_digest": quiescence.digest(),
                            "manifest_digest": digest,
                            "save_evidence_ref": quiescence.save_evidence_ref,
                            "files": manifest,
                        },
                    )
                    try:
                        temporary.rename(cut_dir)
                    except FileExistsError:
                        pass
                finally:
                    if temporary.exists():
                        shutil.rmtree(temporary)
                cut = MinecraftWorldCut(
                    cut_id,
                    _file_ref(payload),
                    _file_ref(manifest_path),
                    quiescence.level_name,
                    quiescence.server_contract_digest,
                    quiescence.process_identity_digest,
                    digest,
                    quiescence.save_evidence_ref,
                )
                self._read_cut(cut)
        except BaseException as exc:
            capture_error = exc

        try:
            self.quiescence.resume(quiescence, session_id=session_id, context=context)
        except BaseException as exc:
            code = "CAPTURE_AND_RESUME_FAILED" if capture_error is not None else "RESUME_FAILED"
            detail = f"resume={type(exc).__name__}: {exc}"
            if capture_error is not None:
                detail = f"capture={type(capture_error).__name__}: {capture_error}; {detail}"
            raise MinecraftWorldCutError(code, detail) from exc
        if capture_error is not None:
            if isinstance(capture_error, (KeyboardInterrupt, SystemExit)):
                raise capture_error
            raise capture_error
        assert cut is not None
        return cut

    def materialize_branch(
        self,
        cut: MinecraftWorldCut,
        *,
        branch_id: str,
        destination_workdir: str,
    ) -> MinecraftWorldBranch:
        if not branch_id.strip():
            raise MinecraftWorldCutError("BRANCH_ID_REQUIRED", "branch_id is empty")
        destination = _safe_child(_local_path(destination_workdir, field="destination_workdir"), self.branch_root, field="destination_workdir")
        payload, document = self._read_cut(cut)
        if destination.exists():
            raise MinecraftWorldCutError("BRANCH_DESTINATION_EXISTS", str(destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.copier.copy(payload, destination)
            if _tree_manifest(destination) != _validated_manifest(document.get("files"), source=str(destination)):
                raise MinecraftWorldCutError("BRANCH_COPY_DIGEST_MISMATCH", branch_id)
            cleanup_ref = "minecraft-branch-cleanup:" + canonical_digest(
                {"branch_id": branch_id, "cut_id": cut.cut_id, "workdir": str(destination)}
            )
            self._publish_metadata(
                destination / "branch.manifest.json",
                {
                    "schema_version": _BRANCH_SCHEMA,
                    "branch_id": branch_id,
                    "cut_id": cut.cut_id,
                    "level_name": cut.level_name,
                    "manifest_digest": cut.manifest_digest,
                    "cleanup_ref": cleanup_ref,
                },
            )
        except BaseException:
            if destination.exists():
                shutil.rmtree(destination)
            raise
        return MinecraftWorldBranch(
            branch_id,
            cut.cut_id,
            str(destination),
            cut.level_name,
            cut.manifest_digest,
            cleanup_ref,
        )

    def release_branch(self, branch: MinecraftWorldBranch) -> str:
        workdir = _safe_child(_local_path(branch.workdir, field="branch.workdir"), self.branch_root, field="branch.workdir")
        manifest_path = workdir / "branch.manifest.json"
        if not manifest_path.is_file():
            raise MinecraftWorldCutError("BRANCH_MANIFEST_MISSING", str(workdir))
        try:
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MinecraftWorldCutError("BRANCH_MANIFEST_INVALID", _safe_exception_message(exc)) from exc
        expected = {
            "schema_version": _BRANCH_SCHEMA,
            "branch_id": branch.branch_id,
            "cut_id": branch.cut_id,
            "level_name": branch.level_name,
            "manifest_digest": branch.manifest_digest,
            "cleanup_ref": branch.cleanup_ref,
        }
        if document != expected:
            raise MinecraftWorldCutError("BRANCH_IDENTITY_MISMATCH", str(workdir))
        try:
            shutil.rmtree(workdir)
        except OSError as exc:
            raise MinecraftWorldCutError(
                "BRANCH_RELEASE_FAILED",
                f"{workdir}: {type(exc).__name__}: {exc}",
            ) from exc
        return branch.cleanup_ref


class MinecraftBranchCheckpointError(RuntimeError):
    """An authoritative branch-world checkpoint could not be restored safely."""


class FilesystemMinecraftBranchCheckpointProvider(MinecraftCheckpointPort):
    """Crash-recoverable branch checkpoint restore over one world authority."""

    _SCHEMA = "minecraft-branch-checkpoint.v1"
    _RESTORE_SCHEMA = "minecraft-branch-checkpoint-restore.v1"
    _RESTORE_PHASES = frozenset({"prepared", "backup_published", "committed"})

    def __init__(
        self,
        *,
        server: MinecraftServerLifecyclePort,
        server_spec: MinecraftServerSpec,
        world_cuts: FilesystemMinecraftWorldCutProvider,
        environment_generation: str,
    ) -> None:
        if not environment_generation.strip():
            raise ValueError("branch checkpoint requires environment generation")
        self._server = server
        self._server_spec = server_spec
        self._world_cuts = world_cuts
        self._environment_generation = environment_generation
        workdir = self._workdir()
        self._restore_journal_path = workdir.parent / f".{workdir.name}.checkpoint-restore.json"
        self._recover_pending_restore()

    def _workdir(self) -> Path:
        return _local_path(self._server_spec.workdir, field="server_workdir")

    def _contract_digest(self) -> str:
        contract = getattr(self._server, "contract", None)
        digest = getattr(contract, "digest", None)
        if not callable(digest):
            raise MinecraftBranchCheckpointError(
                "branch server does not expose an exact service contract digest"
            )
        value = digest()
        if not isinstance(value, str) or len(value) != 64:
            raise MinecraftBranchCheckpointError("branch server contract digest is invalid")
        return value.lower()

    def _restore_document(
        self, *, cut: MinecraftWorldCut, backup: Path, phase: str
    ) -> dict[str, object]:
        if phase not in self._RESTORE_PHASES:
            raise ValueError(f"unsupported restore phase: {phase}")
        document: dict[str, object] = {
            "schema_version": self._RESTORE_SCHEMA,
            "environment_generation": self._environment_generation,
            "server_contract_digest": self._contract_digest(),
            "server_workdir": self._server_spec.workdir,
            "level_name": self._server_spec.level_name,
            "cut_id": cut.cut_id,
            "manifest_digest": cut.manifest_digest,
            "backup_path": str(backup),
            "phase": phase,
        }
        document["record_digest"] = canonical_digest(document)
        return document

    def _publish_restore_document(self, document: Mapping[str, object]) -> dict[str, object]:
        normalized = dict(document)
        payload = {key: value for key, value in normalized.items() if key != "record_digest"}
        normalized["record_digest"] = canonical_digest(payload)
        atomic_replace_bytes(self._restore_journal_path, canonical_bytes(normalized))
        return normalized

    def _set_restore_phase(
        self, document: Mapping[str, object], phase: str
    ) -> dict[str, object]:
        updated = dict(document)
        updated["phase"] = phase
        return self._publish_restore_document(updated)

    def _load_restore_document(self) -> dict[str, object] | None:
        if not self._restore_journal_path.exists():
            return None
        try:
            document = json.loads(self._restore_journal_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MinecraftBranchCheckpointError(
                "branch checkpoint restore journal is unreadable or corrupt"
            ) from exc
        expected = {
            "schema_version",
            "environment_generation",
            "server_contract_digest",
            "server_workdir",
            "level_name",
            "cut_id",
            "manifest_digest",
            "backup_path",
            "phase",
            "record_digest",
        }
        if not isinstance(document, Mapping) or set(document) != expected:
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal schema is invalid")
        record_digest = document.get("record_digest")
        if not isinstance(record_digest, str) or len(record_digest) != 64:
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal digest is invalid")
        payload = {key: value for key, value in document.items() if key != "record_digest"}
        if canonical_digest(payload) != record_digest.lower():
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal digest mismatch")
        if document.get("schema_version") != self._RESTORE_SCHEMA:
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal version mismatch")
        if document.get("environment_generation") != self._environment_generation:
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal generation mismatch")
        if document.get("server_contract_digest") != self._contract_digest():
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal server mismatch")
        if document.get("server_workdir") != self._server_spec.workdir:
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal workdir mismatch")
        if document.get("level_name") != self._server_spec.level_name:
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal level mismatch")
        phase = document.get("phase")
        if phase not in self._RESTORE_PHASES:
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal phase is invalid")
        cut_id = document.get("cut_id")
        if not isinstance(cut_id, str) or not cut_id.strip():
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal cut identity is invalid")
        manifest_digest = document.get("manifest_digest")
        if (
            not isinstance(manifest_digest, str)
            or len(manifest_digest) != 64
            or any(char not in "0123456789abcdef" for char in manifest_digest.lower())
        ):
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal manifest digest is invalid")
        backup_raw = document.get("backup_path")
        if not isinstance(backup_raw, str) or not backup_raw.strip():
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal backup path is invalid")
        workdir = self._workdir()
        backup = _local_path(backup_raw, field="checkpoint_restore_backup")
        expected_prefix = f".{workdir.name}.checkpoint-backup-"
        if backup.parent != workdir.parent or not backup.name.startswith(expected_prefix):
            raise MinecraftBranchCheckpointError("branch checkpoint restore journal backup path is invalid")
        return dict(document)

    def _recover_pending_restore(self) -> str:
        document = self._load_restore_document()
        if document is None:
            return "none"
        workdir = self._workdir()
        backup = _local_path(str(document["backup_path"]), field="checkpoint_restore_backup")
        phase = str(document["phase"])
        if phase == "committed":
            if not workdir.is_dir():
                raise MinecraftBranchCheckpointError(
                    "committed branch checkpoint restore is missing its workdir"
                )
            if backup.exists():
                if backup.is_symlink() or not backup.is_dir():
                    raise MinecraftBranchCheckpointError(
                        "committed branch checkpoint restore backup is not a directory"
                    )
                shutil.rmtree(backup)
                fsync_directory(workdir.parent)
            durable_unlink(self._restore_journal_path)
            return "committed"

        try:
            self._server.stop()
        except BaseException as exc:
            raise MinecraftBranchCheckpointError(
                "branch checkpoint restore recovery could not stop the server; filesystem state was not touched"
            ) from exc

        recovery_errors: list[BaseException] = []
        try:
            if backup.exists():
                if backup.is_symlink() or not backup.is_dir():
                    raise MinecraftBranchCheckpointError(
                        "branch checkpoint restore backup is not a directory"
                    )
                if workdir.exists():
                    if workdir.is_symlink() or not workdir.is_dir():
                        raise MinecraftBranchCheckpointError(
                            "partial restored workdir is not a directory"
                        )
                    shutil.rmtree(workdir)
                backup.rename(workdir)
                fsync_directory(workdir.parent)
            elif not workdir.is_dir():
                raise MinecraftBranchCheckpointError(
                    "branch checkpoint rollback has neither workdir nor backup"
                )
        except BaseException as exc:
            recovery_errors.append(exc)
        try:
            if workdir.is_dir():
                self._server.start()
                self._server.verify_ready()
        except BaseException as exc:
            recovery_errors.append(exc)
        if recovery_errors:
            raise MinecraftBranchCheckpointError(
                "branch checkpoint restore recovery is incomplete: "
                + "; ".join(f"{type(exc).__name__}: {exc}" for exc in recovery_errors)
            ) from recovery_errors[0]
        durable_unlink(self._restore_journal_path)
        return "rolled_back"

    def capture(self, *, session_id: str, context: Any) -> bytes:
        self._recover_pending_restore()
        cut = self._world_cuts.capture(session_id=session_id, context=context)
        document = {
            "schema_version": self._SCHEMA,
            "environment_generation": self._environment_generation,
            "server_contract_digest": self._contract_digest(),
            "server_workdir": self._server_spec.workdir,
            "level_name": self._server_spec.level_name,
            "cut": cut,
        }
        return canonical_bytes(document)

    def _decode(self, payload: bytes) -> MinecraftWorldCut:
        try:
            document = json.loads(payload.decode("utf-8"))
            if document["schema_version"] != self._SCHEMA:
                raise ValueError("unsupported checkpoint schema")
            if document["environment_generation"] != self._environment_generation:
                raise ValueError("environment generation mismatch")
            if document["server_contract_digest"] != self._contract_digest():
                raise ValueError("server contract mismatch")
            if document["server_workdir"] != self._server_spec.workdir:
                raise ValueError("server workdir mismatch")
            if document["level_name"] != self._server_spec.level_name:
                raise ValueError("level name mismatch")
            cut = MinecraftWorldCut(**dict(document["cut"]))
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MinecraftBranchCheckpointError(
                "invalid or incompatible Minecraft branch checkpoint payload"
            ) from exc
        if cut.server_contract_digest != self._contract_digest():
            raise MinecraftBranchCheckpointError(
                "checkpoint cut was captured under a different server contract"
            )
        if cut.level_name != self._server_spec.level_name:
            raise MinecraftBranchCheckpointError("checkpoint cut level identity mismatch")
        return cut

    def restore(self, payload: bytes, *, session_id: str, context: Any) -> None:
        del session_id, context
        self._recover_pending_restore()
        cut = self._decode(payload)
        snapshot, document = self._world_cuts._read_cut(cut)
        expected = _validated_manifest(document.get("files"), source=str(snapshot))
        workdir = self._workdir()
        if not workdir.is_dir():
            raise MinecraftBranchCheckpointError(
                f"branch server workdir is missing before restore: {workdir}"
            )
        backup = workdir.parent / f".{workdir.name}.checkpoint-backup-{uuid4().hex}"
        restore_document = self._publish_restore_document(
            self._restore_document(cut=cut, backup=backup, phase="prepared")
        )
        primary: BaseException | None = None
        try:
            self._server.stop()
            workdir.rename(backup)
            fsync_directory(workdir.parent)
            restore_document = self._set_restore_phase(restore_document, "backup_published")
            self._world_cuts.copier.copy(snapshot, workdir)
            if _tree_manifest(workdir) != expected:
                raise MinecraftBranchCheckpointError(
                    "restored branch workdir does not match checkpoint manifest"
                )
            self._server.start()
            self._server.verify_ready()
            restore_document = self._set_restore_phase(restore_document, "committed")
            shutil.rmtree(backup)
            fsync_directory(workdir.parent)
            durable_unlink(self._restore_journal_path)
            return
        except BaseException as exc:
            primary = exc

        try:
            disposition = self._recover_pending_restore()
        except BaseException as recovery_exc:
            raise MinecraftBranchCheckpointError(
                "Minecraft checkpoint restore failed and crash recovery was incomplete: "
                f"primary={type(primary).__name__}: {primary}; "
                f"recovery={type(recovery_exc).__name__}: {recovery_exc}"
            ) from primary
        if disposition == "committed":
            return
        raise MinecraftBranchCheckpointError(
            f"Minecraft checkpoint restore failed and previous workdir was restored: {primary}"
        ) from primary

class FilesystemMinecraftBranchCheckpointFactory:
    """Bind branch-local RCON save barriers to durable filesystem world cuts."""

    def __init__(
        self,
        *,
        snapshot_root: str | Path,
        materialization_root: str | Path,
        rcon_secret_provider: Callable[[], str],
        copier: MinecraftWorldCopier | None = None,
    ) -> None:
        if not callable(rcon_secret_provider):
            raise ValueError("branch checkpoint RCON secret provider must be callable")
        self._snapshot_root = _local_path(str(snapshot_root), field="checkpoint_snapshot_root")
        self._materialization_root = _local_path(
            str(materialization_root), field="checkpoint_materialization_root"
        )
        self._secret = rcon_secret_provider
        self._copier = copier or FilesystemMinecraftWorldCopier()

    @staticmethod
    def _process_digest(server: MinecraftServerLifecyclePort) -> str:
        reconcile = getattr(server, "reconcile", None)
        if not callable(reconcile):
            raise MinecraftBranchCheckpointError(
                "branch checkpoint requires exact server reconciliation"
            )
        observation = reconcile()
        process = getattr(observation, "process", None)
        if process is None:
            raise MinecraftBranchCheckpointError(
                "branch server process identity is unavailable"
            )
        return canonical_digest(process)

    def create(
        self,
        *,
        server: MinecraftServerLifecyclePort,
        server_spec: MinecraftServerSpec,
        environment_generation: str,
    ) -> MinecraftCheckpointPort:
        rcon: MinecraftRconEndpoint | None = server_spec.rcon_endpoint
        if rcon is None:
            raise MinecraftBranchCheckpointError(
                "authoritative branch checkpoint requires an RCON endpoint"
            )
        contract = getattr(server, "contract", None)
        digest = getattr(contract, "digest", None)
        if not callable(digest):
            raise MinecraftBranchCheckpointError(
                "branch checkpoint requires an exact server contract"
            )
        console = MinecraftRconConsole(rcon, secret_provider=self._secret)
        quiescence = MinecraftSaveQuiescenceProvider(
            console=console,
            source_workdir=server_spec.workdir,
            level_name=server_spec.level_name,
            server_contract_digest=digest(),
            process_identity_digest=lambda: self._process_digest(server),
        )
        world_cuts = FilesystemMinecraftWorldCutProvider(
            quiescence=quiescence,
            snapshot_root=self._snapshot_root,
            branch_root=self._materialization_root,
            copier=self._copier,
        )
        return FilesystemMinecraftBranchCheckpointProvider(
            server=server,
            server_spec=server_spec,
            world_cuts=world_cuts,
            environment_generation=environment_generation,
        )


__all__ = [
    "FilesystemMinecraftBranchCheckpointFactory",
    "FilesystemMinecraftBranchCheckpointProvider",
    "FilesystemMinecraftWorldCopier",
    "FilesystemMinecraftWorldCutProvider",
    "MinecraftWorldCopier",
    "MinecraftWorldCutError",
    "MinecraftBranchCheckpointError",
    "ReflinkMinecraftWorldCopier",
]
