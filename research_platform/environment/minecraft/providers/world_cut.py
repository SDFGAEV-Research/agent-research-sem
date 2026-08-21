from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Protocol

from research_platform.platform.kernel import canonical_digest
from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes

from ..api import (
    MinecraftWorldBranch,
    MinecraftWorldCut,
    MinecraftWorldCutPort,
    MinecraftWorldQuiescence,
    MinecraftWorldQuiescencePort,
)


_CUT_SCHEMA = "minecraft-world-cut.v1"
_BRANCH_SCHEMA = "minecraft-world-branch.v1"
_EXCLUDED_DIRECTORIES = frozenset({"logs", "crash-reports"})
_EXCLUDED_FILES = frozenset({"session.lock"})


class MinecraftWorldCutError(RuntimeError):
    """A world-cut or branch operation failed with a stable cause code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"Minecraft world cut failed [{code}]: {message}")
        self.code = code


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _local_path(value: str, *, field: str) -> Path:
    path = Path(value).expanduser().resolve(strict=False)
    if not path.is_absolute():
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
    for path in source.rglob("*"):
        if path.is_symlink():
            raise MinecraftWorldCutError("SYMLINK_UNSUPPORTED", str(path))


def _tree_manifest(root: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if _excluded(relative):
            continue
        if path.is_symlink():
            raise MinecraftWorldCutError("SYMLINK_UNSUPPORTED", str(path))
        if path.is_file():
            rows.append(
                {
                    "path": relative.as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
        elif not path.is_dir():
            raise MinecraftWorldCutError("UNSUPPORTED_FILE_TYPE", str(path))
    if not rows:
        raise MinecraftWorldCutError("SOURCE_EMPTY", str(root))
    return tuple(rows)


def _manifest_digest(manifest: tuple[dict[str, object], ...]) -> str:
    return canonical_digest(manifest)


def _metadata_bytes(value: Mapping[str, object]) -> bytes:
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
    """Linux copier that requires copy-on-write support instead of falling back."""

    def __init__(
        self,
        *,
        cp_executable: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        platform_name: str | None = None,
    ) -> None:
        self.cp_executable = cp_executable
        self.runner = runner or subprocess.run
        self.platform_name = platform_name or os.name

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


def _portable_metadata_writer(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _default_metadata_writer(path: Path, payload: bytes) -> None:
    """Select the host's explicit metadata durability capability.

    Linux deployment uses the platform's directory-fsync publication. Windows
    controllers cannot fsync a directory through the same API, so they use an
    atomic replace for local contract tests; they do not claim POSIX crash
    durability.
    """

    if os.name == "nt":
        _portable_metadata_writer(path, payload)
        return
    atomic_replace_bytes(path, payload)


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
    ) -> None:
        self.quiescence = quiescence
        self.snapshot_root = _local_path(str(snapshot_root), field="snapshot_root")
        self.branch_root = _local_path(str(branch_root), field="branch_root")
        if self.snapshot_root == self.branch_root or _within(self.snapshot_root, self.branch_root) or _within(self.branch_root, self.snapshot_root):
            raise ValueError("snapshot_root and branch_root must be disjoint")
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        self.branch_root.mkdir(parents=True, exist_ok=True)
        self.copier = copier or FilesystemMinecraftWorldCopier()
        self.metadata_writer = metadata_writer or _default_metadata_writer

    @staticmethod
    def _identity_path(root: Path, identity: str) -> Path:
        return root / hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def _cut_dir(self, cut_id: str) -> Path:
        return self._identity_path(self.snapshot_root / "cuts", cut_id)

    def _publish_metadata(self, path: Path, value: Mapping[str, object]) -> None:
        self.metadata_writer(path, _metadata_bytes(value))

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
            raise MinecraftWorldCutError("SNAPSHOT_MANIFEST_INVALID", str(exc)) from exc
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
            raise MinecraftWorldCutError("BRANCH_MANIFEST_INVALID", str(exc)) from exc
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


__all__ = [
    "FilesystemMinecraftWorldCopier",
    "FilesystemMinecraftWorldCutProvider",
    "MinecraftWorldCopier",
    "MinecraftWorldCutError",
    "ReflinkMinecraftWorldCopier",
]
