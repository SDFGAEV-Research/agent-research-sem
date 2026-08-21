from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from research_platform.environment.minecraft.api import (
    MinecraftWorldQuiescence,
)
from research_platform.environment.minecraft.providers.world_cut import (
    FilesystemMinecraftWorldCopier,
    FilesystemMinecraftWorldCutProvider,
    MinecraftWorldCutError,
    ReflinkMinecraftWorldCopier,
)


class _QuiescenceDouble:
    def __init__(self, source_workdir: str) -> None:
        self.source_workdir = source_workdir
        self.saved: list[tuple[str, object]] = []
        self.resumed: list[tuple[str, str]] = []
        self.resume_error: BaseException | None = None

    def save_and_quiesce(self, *, session_id: str, context: object) -> MinecraftWorldQuiescence:
        self.saved.append((session_id, context))
        return MinecraftWorldQuiescence(
            source_workdir=self.source_workdir,
            level_name="research-world",
            server_contract_digest="a" * 64,
            process_identity_digest="b" * 64,
            save_evidence_ref="minecraft-save-evidence:test",
        )

    def resume(
        self,
        quiescence: MinecraftWorldQuiescence,
        *,
        session_id: str,
        context: object,
    ) -> None:
        del context
        self.resumed.append((session_id, quiescence.save_evidence_ref))
        if self.resume_error is not None:
            raise self.resume_error


def _portable_metadata_writer(path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _source_world(tmp_path):
    source = tmp_path / "source-world"
    level = source / "research-world"
    level.mkdir(parents=True)
    (source / "server.properties").write_text("level-name=research-world\n", encoding="utf-8")
    (source / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    (level / "level.dat").write_bytes(b"level-dat")
    (level / "region").mkdir()
    (level / "region" / "r.0.0.mca").write_bytes(b"region")
    (source / "logs").mkdir()
    (source / "logs" / "latest.log").write_bytes(b"volatile log")
    (source / "crash-reports").mkdir()
    (source / "crash-reports" / "crash.txt").write_bytes(b"volatile crash")
    (level / "session.lock").write_bytes(b"volatile lock")
    return source


def _provider(tmp_path, source):
    quiescence = _QuiescenceDouble(str(source))
    provider = FilesystemMinecraftWorldCutProvider(
        quiescence=quiescence,
        snapshot_root=tmp_path / "cuts",
        branch_root=tmp_path / "branches",
        metadata_writer=_portable_metadata_writer,
    )
    return provider, quiescence


def test_world_cut_capture_materializes_verified_branch_and_releases_it(tmp_path) -> None:
    source = _source_world(tmp_path)
    provider, control = _provider(tmp_path, source)

    cut = provider.capture(session_id="session-1", context=None)

    assert control.saved == [("session-1", None)]
    assert control.resumed == [("session-1", "minecraft-save-evidence:test")]
    manifest = json.loads((tmp_path / "cuts").rglob("manifest.json").__next__().read_text())
    paths = {row["path"] for row in manifest["files"]}
    assert "research-world/level.dat" in paths
    assert "logs/latest.log" not in paths
    assert "research-world/session.lock" not in paths

    branch = provider.materialize_branch(
        cut,
        branch_id="candidate-1",
        destination_workdir=str(tmp_path / "branches" / "candidate-1"),
    )
    assert (tmp_path / "branches" / "candidate-1" / "research-world" / "level.dat").read_bytes() == b"level-dat"
    assert not (tmp_path / "branches" / "candidate-1" / "logs").exists()
    assert provider.release_branch(branch) == branch.cleanup_ref
    assert not (tmp_path / "branches" / "candidate-1").exists()


def test_reflink_copier_requires_reflink_and_never_silently_falls_back(tmp_path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 1, "", "reflink unsupported")

    copier = ReflinkMinecraftWorldCopier(
        cp_executable="cp",
        runner=runner,
        platform_name="posix",
    )
    with pytest.raises(MinecraftWorldCutError, match="REFLINK_COPY_FAILED"):
        copier.copy(tmp_path / "source", tmp_path / "destination")
    assert "--reflink=always" in calls[0][0]
    assert "--reflink=auto" not in calls[0][0]


def test_reflink_copier_uses_only_explicit_fallback_and_reports_capability_failure(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "world.dat").write_bytes(b"world")
    reasons: list[str] = []

    def runner(command, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(command, 1, "", "Operation not supported")

    copier = ReflinkMinecraftWorldCopier(
        cp_executable="cp",
        runner=runner,
        platform_name="posix",
        fallback_copier=FilesystemMinecraftWorldCopier(),
        fallback_reporter=reasons.append,
    )
    destination = tmp_path / "destination"
    copier.copy(source, destination)

    assert (destination / "world.dat").read_bytes() == b"world"
    assert reasons == ["Operation not supported"]


def test_reflink_copier_rejects_non_posix_target_explicitly(tmp_path) -> None:
    copier = ReflinkMinecraftWorldCopier(platform_name="nt")
    with pytest.raises(MinecraftWorldCutError, match="REFLINK_UNSUPPORTED_PLATFORM"):
        copier.copy(tmp_path / "source", tmp_path / "destination")


def test_reflink_copier_prunes_nested_volatile_entries_after_verified_copy(tmp_path) -> None:
    def runner(command, **kwargs):
        del kwargs
        destination = Path(command[-1])
        (destination / "nested" / "logs").mkdir(parents=True)
        (destination / "nested" / "logs" / "latest.log").write_text("volatile")
        (destination / "nested" / "session.lock").write_text("volatile")
        (destination / "research-world").mkdir()
        (destination / "research-world" / "level.dat").write_bytes(b"level")
        return subprocess.CompletedProcess(command, 0, "", "")

    destination = tmp_path / "destination"
    ReflinkMinecraftWorldCopier(
        cp_executable="cp",
        runner=runner,
        platform_name="posix",
    ).copy(tmp_path / "source", destination)

    assert not (destination / "nested" / "logs").exists()
    assert not (destination / "nested" / "session.lock").exists()


def test_world_cut_default_metadata_writer_matches_controller_platform(tmp_path) -> None:
    source = _source_world(tmp_path)
    control = _QuiescenceDouble(str(source))
    provider = FilesystemMinecraftWorldCutProvider(
        quiescence=control,
        snapshot_root=tmp_path / "cuts",
        branch_root=tmp_path / "branches",
    )

    cut = provider.capture(session_id="session-1", context=None)

    assert cut.manifest_digest
    assert control.resumed == [("session-1", "minecraft-save-evidence:test")]


def test_world_cut_rejects_tampered_snapshot_before_branch_copy(tmp_path) -> None:
    source = _source_world(tmp_path)
    provider, _control = _provider(tmp_path, source)
    cut = provider.capture(session_id="session-1", context=None)

    payload = tmp_path / "cuts" / "cuts"
    payload_file = next(payload.rglob("payload/research-world/level.dat"))
    payload_file.write_bytes(b"tampered")

    with pytest.raises(MinecraftWorldCutError, match="SNAPSHOT_CONTENT_MISMATCH"):
        provider.materialize_branch(
            cut,
            branch_id="candidate-1",
            destination_workdir=str(tmp_path / "branches" / "candidate-1"),
        )
    assert not (tmp_path / "branches" / "candidate-1").exists()


def test_world_cut_preserves_capture_error_when_resume_succeeds(tmp_path) -> None:
    source = tmp_path / "source-world"
    source.mkdir()
    provider, control = _provider(tmp_path, source)

    with pytest.raises(MinecraftWorldCutError, match="SOURCE_LEVEL_MISSING"):
        provider.capture(session_id="session-1", context=None)
    assert control.resumed == [("session-1", "minecraft-save-evidence:test")]


def test_world_cut_reports_resume_failure_without_claiming_capture_success(tmp_path) -> None:
    source = _source_world(tmp_path)
    provider, control = _provider(tmp_path, source)
    control.resume_error = RuntimeError("server did not resume")

    with pytest.raises(MinecraftWorldCutError, match="RESUME_FAILED") as raised:
        provider.capture(session_id="session-1", context=None)
    assert raised.value.code == "RESUME_FAILED"
