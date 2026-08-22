from __future__ import annotations

from pathlib import Path

from research_platform.governance.release.runtime.manifest import _iter_release_files


def test_release_file_projection_excludes_controller_state_and_local_profiles(tmp_path: Path) -> None:
    (tmp_path / ".server-state" / "server-sessions").mkdir(parents=True)
    (tmp_path / ".server-state" / "server-sessions" / "operations.jsonl").write_text(
        "private controller evidence", encoding="utf-8"
    )
    (tmp_path / "configs" / "server_profiles").mkdir(parents=True)
    (tmp_path / "configs" / "server_profiles" / "sem-ubuntu.validation.local.env").write_text(
        "RP_SERVER_SEM_UBUNTU_HOST=private", encoding="utf-8"
    )
    (tmp_path / "configs" / "server_profiles" / "example.env").write_text(
        "RP_SERVER_CATALOG_IDS=sem-ubuntu", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("public", encoding="utf-8")

    paths = {relative.as_posix() for _path, relative in _iter_release_files(tmp_path)}
    assert "README.md" in paths
    assert "configs/server_profiles/example.env" in paths
    assert ".server-state/server-sessions/operations.jsonl" not in paths
    assert "configs/server_profiles/sem-ubuntu.validation.local.env" not in paths
