from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from research_platform.environment.minecraft.api import MinecraftRconEndpoint, MinecraftServerSpec
from research_platform.environment.minecraft.composition import (
    MinecraftServerServiceError,
    MinecraftServerServiceFactory,
    MinecraftServerServiceFactoryConfig,
)
from research_platform.environment.minecraft.providers.server_files import MinecraftServerPreparationError, sha256_file
from research_platform.runtime.host.providers import LocalOperatingSystemRoute
from research_platform.runtime.service.runtime.environment import MaterializedServiceEnvironment


def _spec(root: Path) -> MinecraftServerSpec:
    jar = root / "server.jar"
    jar.write_bytes(b"frozen-minecraft-server-artifact")
    return MinecraftServerSpec(
        jar_path=str(jar),
        workdir=str(root / "world"),
        java_executable="C:/Java/bin/java.exe",
        host="127.0.0.1",
        port=25566,
        level_name="branch-world",
    )


def _config(root: Path, *, accept_eula: bool) -> MinecraftServerServiceFactoryConfig:
    return MinecraftServerServiceFactoryConfig(
        environment=MaterializedServiceEnvironment.from_mapping(
            {"JAVA_HOME": "C:/Java"},
            "env:evidence",
        ),
        state_root=root / "state",
        intent_root=root / "intents",
        capture_root=root / "captures",
        operating_system=LocalOperatingSystemRoute(),
        accept_eula=accept_eula,
        process_backend=object(),
    )


def test_server_factory_prepares_files_and_builds_exact_service_contract_without_starting(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    controller = MinecraftServerServiceFactory(_config(tmp_path, accept_eula=True)).create(
        spec,
        environment_generation="e" * 64,
    )

    assert controller.contract.artifact_digest == sha256_file(spec.jar_path)
    assert len(controller.contract.generation) == 64
    assert (Path(spec.workdir) / "eula.txt").read_text(encoding="utf-8") == "eula=true\n"
    assert (Path(spec.workdir) / "server.properties").is_file()


def test_server_factory_requires_explicit_eula_policy(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    with pytest.raises(MinecraftServerPreparationError, match="EULA_ACCEPTANCE_REQUIRED"):
        MinecraftServerServiceFactory(_config(tmp_path, accept_eula=False)).create(
            spec,
            environment_generation="e" * 64,
        )


def test_server_factory_sanitizes_rcon_secret_provider_failure(tmp_path: Path) -> None:
    spec = replace(_spec(tmp_path), rcon_endpoint=MinecraftRconEndpoint())
    config = replace(
        _config(tmp_path, accept_eula=True),
        rcon_password_provider=lambda: (_ for _ in ()).throw(RuntimeError("secret-value")),
    )
    with pytest.raises(MinecraftServerServiceError) as caught:
        MinecraftServerServiceFactory(config).create(spec, environment_generation="e" * 64)
    assert "secret-value" not in str(caught.value)
    assert "secret is unavailable" in str(caught.value)
