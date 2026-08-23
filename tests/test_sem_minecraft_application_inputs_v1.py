from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from research_platform.experimentation.run.runtime import DirectoryRunArtifactStore
from scripts import sem_paper_minecraft_application as application


def _clear_sem_mc_environment(monkeypatch) -> None:
    for name in (
        "SEM_MC_SERVER_JAR",
        "SEM_MC_SERVER_LIBRARIES_DIR",
        "SEM_MC_QUALIFIED_MODEL_CLOSURE",
        "SEM_MC_TASKS",
        "SEM_MC_SCENARIO",
        "SEM_MC_NODE",
        "SEM_MC_JAVA",
    ):
        monkeypatch.delenv(name, raising=False)


def test_scripted_smoke_defaults_to_deterministic_tasks_scenario_and_asset_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _clear_sem_mc_environment(monkeypatch)

    inputs = application.parse_inputs(
        [
            "--mode",
            "scripted-smoke",
            "--run-id",
            "smoke-defaults",
            "--output-dir",
            str(tmp_path / "run"),
        ]
    )

    assert inputs.tasks_path.name == "scripted_smoke.json"
    assert inputs.scenario_path is not None
    assert inputs.scenario_path.name == "scripted_smoke_scenario.json"
    assert inputs.server_jar.as_posix().endswith(
        ".runtime-assets/minecraft/1.21.8/server.jar"
    )
    assert inputs.acquire_server_jar is False
    assert [task.family for task in application.load_tasks(inputs.tasks_path, ())] == [
        "gather",
        "craft",
        "craft",
        "interaction",
        "combat",
    ]
    assert application.load_scenario(inputs.scenario_path).scenario_id == (
        "sem-paper.minecraft.scripted-smoke"
    )


def test_missing_server_artifact_reports_explicit_acquisition_route(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _clear_sem_mc_environment(monkeypatch)
    inputs = application.parse_inputs(
        [
            "--mode",
            "preflight",
            "--run-id",
            "missing-server",
            "--output-dir",
            str(tmp_path / "run"),
            "--server-jar",
            str(tmp_path / "missing.jar"),
        ]
    )

    with pytest.raises(application.ExperimentConfigurationError, match="acquire-server-jar"):
        application._ensure_server_artifact(
            inputs,
            DirectoryRunArtifactStore(inputs.output_dir),
        )


def test_task_manifest_rejects_invalid_script_action_before_live_launch() -> None:
    with pytest.raises(ValueError, match="FIELD_RANGE"):
        application.task_from_mapping(
            {
                "task_id": "invalid-action",
                "family": "combat",
                "goal": "invalid bounded action",
                "script": [
                    {
                        "tool": "attack_nearest",
                        "args": {"entity": "husk", "max_hits": 999},
                    }
                ],
            }
        )


def test_explicit_server_acquisition_publishes_verified_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _clear_sem_mc_environment(monkeypatch)
    inputs = application.parse_inputs(
        [
            "--mode",
            "preflight",
            "--run-id",
            "acquire-server",
            "--output-dir",
            str(tmp_path / "run"),
            "--server-jar",
            str(tmp_path / "asset" / "server.jar"),
            "--acquire-server-jar",
        ]
    )

    class Provider:
        def acquire(self, version, *, destination, scope, producer_operation_id, timeout_s):
            assert version == "1.21.8"
            assert scope.scope_id == "sem-paper-1"
            assert producer_operation_id == inputs.execution_attempt_id
            assert timeout_s == inputs.server_artifact_timeout_s
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"verified-server")
            return SimpleNamespace(
                record=SimpleNamespace(
                    artifact_id="minecraft.server.1.21.8",
                    location=str(path),
                    metadata=(("source_url", "https://piston-data.mojang.com/server.jar"),),
                    producer_operation_id=producer_operation_id,
                ),
                downloaded=True,
                sha256="a" * 64,
                sha1="b" * 40,
                size=len(b"verified-server"),
            )

    monkeypatch.setattr(
        application,
        "compose_official_minecraft_server_artifacts",
        lambda: SimpleNamespace(provider=Provider()),
    )
    artifacts = DirectoryRunArtifactStore(inputs.output_dir)

    application._ensure_server_artifact(inputs, artifacts)

    assert inputs.server_jar.read_bytes() == b"verified-server"
    assert (inputs.output_dir / "server_artifact.json").is_file()
