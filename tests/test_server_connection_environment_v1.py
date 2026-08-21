from __future__ import annotations

from pathlib import Path

import pytest

from research_platform.runtime.server.identity.api import (
    ServerCommandResult,
    ServerIdentityConfigurationError,
    server_environment_prefix,
)
from research_platform.runtime.server.identity.providers import (
    EnvironmentSSHServerConnectionFactory,
    SSHServerConnection,
)
from research_platform.runtime.host.providers import LocalOperatingSystemRoute


OS_ROUTE = LocalOperatingSystemRoute()


def test_environment_profile_materializes_without_secret_or_address_in_source() -> None:
    prefix = server_environment_prefix("sem-ubuntu")
    connection = EnvironmentSSHServerConnectionFactory(OS_ROUTE, ssh_executable="ssh-test").from_environment(
        "sem-ubuntu",
        environ={
            f"{prefix}_HOST": "research.example",
            f"{prefix}_PORT": "60320",
            f"{prefix}_USER": "ubuntu",
            f"{prefix}_KEY_PATH": str(Path("/keys/research")),
        },
    )
    assert connection.profile.destination == "ubuntu@research.example"
    assert connection.profile.port == 60320


def test_environment_profile_rejects_missing_required_fields() -> None:
    with pytest.raises(ServerIdentityConfigurationError, match="_HOST"):
        EnvironmentSSHServerConnectionFactory(OS_ROUTE).from_environment(
            "sem-ubuntu",
            environ={
                "RP_SERVER_SEM_UBUNTU_PORT": "22",
                "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
            },
        )


def test_ssh_provider_builds_argv_without_password_or_local_shell() -> None:
    captured: list[tuple[tuple[str, ...], bool]] = []

    def runner(argv: tuple[str, ...], *, interactive: bool) -> ServerCommandResult:
        captured.append((argv, interactive))
        return ServerCommandResult("sem-ubuntu", "hostname", 0, "host=box\n", "")

    connection = SSHServerConnection(
        EnvironmentSSHServerConnectionFactory(OS_ROUTE, ssh_executable="ssh-test").from_environment(
            "sem-ubuntu",
            environ={
                "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
                "RP_SERVER_SEM_UBUNTU_PORT": "60320",
                "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
            },
        ).profile,
        operating_system=OS_ROUTE,
        runner=runner,
    )
    result = connection.execute("hostname")
    assert result.succeeded
    assert captured == [
        (("ssh-test", "-p", "60320", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", "ubuntu@research.example", "hostname"), False)
    ]


def test_health_parses_machine_facts_from_one_remote_command() -> None:
    profile = EnvironmentSSHServerConnectionFactory(OS_ROUTE, ssh_executable="ssh-test").from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
        },
    ).profile

    def runner(argv: tuple[str, ...], *, interactive: bool) -> ServerCommandResult:
        return ServerCommandResult(
            "sem-ubuntu",
            argv[-1],
            0,
            "host=box\npython=Python 3.11.9\ngit=git version 2.43.0\ntmux=tmux 3.4\n",
            "",
        )

    report = SSHServerConnection(profile, operating_system=OS_ROUTE, runner=runner).health()
    assert report.reachable
    assert report.host_name == "box"
    assert report.python_version == "Python 3.11.9"
    assert report.tmux_version == "tmux 3.4"
