from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from research_platform.platform.kernel import canonical_bytes, canonical_digest
from research_platform.platform.kernel.durability.durable_file import (
    atomic_replace_bytes,
    durable_unlink,
    fsync_directory,
)

from ..api import (
    MinecraftCheckpointPort,
    MinecraftRconEndpoint,
    MinecraftServerLifecyclePort,
    MinecraftServerSpec,
    MinecraftWorldCut,
)
from .rcon import MinecraftRconConsole
from .world_copy import FilesystemMinecraftWorldCopier, MinecraftWorldCopier
from .world_cut_integrity import (
    local_path as _local_path,
    tree_manifest as _tree_manifest,
    validated_manifest as _validated_manifest,
)
from .world_cut_provider import FilesystemMinecraftWorldCutProvider
from .world_quiescence import MinecraftSaveQuiescenceProvider

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
    "MinecraftBranchCheckpointError",
]
