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
        "SEM_MC_JAVA_FEATURE_VERSION",
        "SEM_MC_JAVA_RUNTIME_CACHE",
        "SEM_MC_JAVA_RUNTIME_TIMEOUT_S",
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
    assert inputs.acquire_java_runtime is False
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


def test_explicit_java_runtime_acquisition_resolves_a_platform_cache_without_host_java(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _clear_sem_mc_environment(monkeypatch)
    cache = tmp_path / "java-cache"

    inputs = application.parse_inputs(
        [
            "--mode",
            "preflight",
            "--run-id",
            "acquire-java",
            "--output-dir",
            str(tmp_path / "run"),
            "--acquire-java-runtime",
            "--java-runtime-cache",
            str(cache),
        ]
    )

    assert inputs.acquire_java_runtime is True
    assert inputs.java_feature_version == 21
    assert inputs.java_runtime_cache == cache.resolve()
    assert inputs.java_executable == str(cache.resolve() / "home" / "bin" / "java")
    assert inputs.java_runtime_receipt_digest is None


def test_explicit_java_runtime_acquisition_publishes_verified_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _clear_sem_mc_environment(monkeypatch)
    inputs = application.parse_inputs(
        [
            "--mode",
            "preflight",
            "--run-id",
            "provision-java",
            "--output-dir",
            str(tmp_path / "run"),
            "--acquire-java-runtime",
            "--java-runtime-cache",
            str(tmp_path / "java-cache"),
        ]
    )
    java = Path(inputs.java_executable)
    java.parent.mkdir(parents=True, exist_ok=True)
    java.write_bytes(b"verified-java")
    java.chmod(0o755)
    receipt = application.JavaRuntimeReceipt(
        provider_id="eclipse-adoptium.temurin.v3",
        feature_version=21,
        semantic_version="21.0.8+9",
        release_name="jdk-21.0.8+9",
        operating_system="linux",
        architecture="x64",
        metadata_url="https://api.adoptium.net/v3/assets/latest/21/hotspot",
        source_url=(
            "https://github.com/adoptium/temurin21-binaries/releases/download/"
            "jdk-21.0.8%2B9/archive.tar.gz"
        ),
        archive_path=str(inputs.java_runtime_cache / "archive.tar.gz"),
        archive_sha256="a" * 64,
        archive_size=10,
        java_home=str(inputs.java_runtime_cache / "home"),
        java_executable=str(java),
        java_executable_sha256="b" * 64,
        materialized_tree_sha256="c" * 64,
        materialized_file_count=1,
        materialized_size=10,
        java_major=21,
        java_version_output_sha256="d" * 64,
    )

    class Provisioner:
        def provision(self, request):
            assert request.feature_version == 21
            assert request.destination == str(inputs.java_runtime_cache / "home")
            assert request.producer_operation_id == inputs.execution_attempt_id
            return SimpleNamespace(
                receipt=receipt,
                archive_downloaded=True,
                materialized=True,
            )

    monkeypatch.setattr(
        application,
        "compose_eclipse_adoptium_java_runtime",
        lambda: SimpleNamespace(provisioner=Provisioner()),
    )
    artifacts = DirectoryRunArtifactStore(inputs.output_dir)

    effective, effective_receipt = application._ensure_java_runtime(inputs, artifacts)

    assert effective_receipt == receipt
    assert effective.java_runtime_receipt_digest == receipt.digest()
    assert (inputs.output_dir / "java_runtime_artifact.json").is_file()


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
