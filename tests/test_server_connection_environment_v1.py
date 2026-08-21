from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from research_platform.runtime.server.identity.api import (
    ServerCommandResult,
    ServerFileTransferResult,
    ServerIdentityConfigurationError,
    ServerTransportFailureKind,
    server_environment_prefix,
)
from research_platform.runtime.server.health.api import ServerRuntimeHealthSpec
from research_platform.runtime.server.health.providers import SSHServerHealthProbe
from research_platform.runtime.server.identity.providers import (
    EnvironmentSSHServerConnectionFactory,
    EnvironmentSSHServerFileTransferFactory,
    SSHServerConnection,
    SSHServerFileTransfer,
)
from research_platform.runtime.host.providers import LocalOperatingSystemRoute
from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.runtime.host.composition import compose_local_host
from research_platform.runtime.server.identity.composition import (
    compose_environment_server_identity,
)


OS_ROUTE = LocalOperatingSystemRoute()


def test_server_identity_composition_records_the_host_route_binding() -> None:
    meta = build_in_memory_platform_meta()
    host = compose_local_host(planner=meta.capability_composition)
    composed = compose_environment_server_identity(
        operating_system=host.operating_system,
        host_operating_system_offer=host.operating_system_offer,
        planner=meta.capability_composition,
    )
    connection = composed.connection_factory.from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
        },
    )
    assert connection.profile.destination == "ubuntu@research.example"
    assert len(composed.plan.edges) == 1
    assert composed.plan.edges[0].offer.offer_id == host.operating_system_offer.offer_id


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


def test_ssh_provider_reuses_one_explicit_control_path_for_interactive_operations(tmp_path: Path) -> None:
    captured: list[tuple[tuple[str, ...], bool]] = []

    def runner(argv: tuple[str, ...], *, interactive: bool) -> ServerCommandResult:
        captured.append((argv, interactive))
        return ServerCommandResult("sem-ubuntu", "hostname", 0, "host=box\n", "")

    connection = EnvironmentSSHServerConnectionFactory(OS_ROUTE, ssh_executable="ssh-test").from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
            "RP_SERVER_SEM_UBUNTU_SSH_CONTROL_PATH": "/tmp/rp-ssh-%C",
            "RP_SERVER_SEM_UBUNTU_SSH_CONTROL_PERSIST_SECONDS": "900",
        },
    )
    SSHServerConnection(connection.profile, operating_system=OS_ROUTE, runner=runner).execute(
        "hostname", interactive=True
    )
    argv = captured[0][0]
    assert "ControlMaster=auto" in argv
    assert "ControlPersist=900" in argv
    assert "ControlPath=/tmp/rp-ssh-%C" in argv


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

    report = SSHServerHealthProbe().probe(
        SSHServerConnection(profile, operating_system=OS_ROUTE, runner=runner)
    )
    assert report.reachable
    assert report.host_name == "box"
    assert report.python_version == "Python 3.11.9"
    assert report.tmux_version == "tmux 3.4"


def test_managed_health_verifies_python_package_identity() -> None:
    package_digest = "b" * 64
    specification = ServerRuntimeHealthSpec(
        platform_root="/srv/research-platform",
        release_root="/srv/research-platform/releases",
        remote_home="/home/ubuntu",
        python_executable="/srv/research-platform/envs/sem/bin/python",
        python_binary_sha256="c" * 64,
        python_packages_sha256=package_digest,
        node_executable="/srv/toolchains/node/bin/node",
        node_binary_sha256="d" * 64,
        java_executable="/srv/toolchains/java/bin/java",
        java_binary_sha256="e" * 64,
        platform_management_executable="/srv/research-platform/bin/research-platform-manage",
        platform_management_binary_sha256="f" * 64,
        tmux_executable="/usr/local/bin/tmux",
        sha256sum_executable="/usr/bin/sha256sum",
        tmux_binary_sha256="a" * 64,
    )

    def runner(argv: tuple[str, ...], *, interactive: bool) -> ServerCommandResult:
        return ServerCommandResult(
            "sem-ubuntu",
            argv[-1],
            0,
            "host=box\n"
            "python_version=Python 3.11.15\n"
            "python_packages_status=0\n"
            f"python_packages_digest={package_digest}  -\n"
            "python_binary_digest=" + "c" * 64 + "  /srv/research-platform/envs/sem/bin/python\n"
            "node_binary_digest=" + "d" * 64 + "  /srv/toolchains/node/bin/node\n"
            "java_binary_digest=" + "e" * 64 + "  /srv/toolchains/java/bin/java\n"
            "platform_management_binary_digest=" + "f" * 64 + "  /srv/research-platform/bin/research-platform-manage\n"
            "tmux_digest=" + "a" * 64 + "  /usr/local/bin/tmux\n"
            "remote_home=present\nplatform_root=present\nrelease_root=present\n"
            "python_executable=present\nnode_executable=present\njava_executable=present\n"
            "platform_management_executable=present\ntmux_executable=present\nsha256sum_executable=present\n",
            "",
        )

    report = SSHServerHealthProbe().probe(
        SSHServerConnection(
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
        ),
        specification=specification,
    )
    assert report.platform_ready
    assert dict(report.checks)["python_packages_identity"] == "verified"


def test_scp_transfer_builds_argv_without_password_and_requires_absolute_posix_target(tmp_path: Path) -> None:
    local = tmp_path / "release.zip"
    local.write_bytes(b"release")
    captured: list[tuple[tuple[str, ...], bool]] = []

    def runner(argv: tuple[str, ...], *, interactive: bool) -> ServerFileTransferResult:
        captured.append((argv, interactive))
        return ServerFileTransferResult("sem-ubuntu", str(local), "/srv/releases/release.zip", 0, "", "")

    profile = EnvironmentSSHServerFileTransferFactory(OS_ROUTE, scp_executable="scp-test").from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
        },
    ).profile
    transfer = SSHServerFileTransfer(
        profile,
        operating_system=OS_ROUTE,
        scp_executable="scp-test",
        runner=runner,
    )
    result = transfer.upload(str(local), "/srv/releases/release.zip")
    assert result.succeeded
    assert transfer.executable == "scp-test"
    assert captured == [
        (
            (
                "scp-test",
                "-P",
                "60320",
                "-o",
                "ConnectTimeout=15",
                "-B",
                str(local),
                "ubuntu@research.example:/srv/releases/release.zip",
            ),
            False,
        )
    ]
    with pytest.raises(ValueError, match="absolute POSIX"):
        transfer.upload(str(local), "relative/release.zip")


def test_scp_download_builds_reverse_argv_and_requires_absolute_local_target(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    captured: list[tuple[tuple[str, ...], bool]] = []

    def runner(argv: tuple[str, ...], *, interactive: bool) -> ServerFileTransferResult:
        captured.append((argv, interactive))
        return ServerFileTransferResult("sem-ubuntu", str(target), "/data/results/result.json", 0, "", "")

    profile = EnvironmentSSHServerFileTransferFactory(OS_ROUTE, scp_executable="scp-test").from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
        },
    ).profile
    transfer = SSHServerFileTransfer(
        profile,
        operating_system=OS_ROUTE,
        scp_executable="scp-test",
        runner=runner,
    )
    result = transfer.download("/data/results/result.json", str(target))
    assert result.succeeded
    assert captured == [
        (
            (
                "scp-test",
                "-P",
                "60320",
                "-o",
                "ConnectTimeout=15",
                "-B",
                "ubuntu@research.example:/data/results/result.json",
                str(target),
            ),
            False,
        )
    ]
    with pytest.raises(ValueError, match="absolute local"):
        transfer.download("/data/results/result.json", "relative/result.json")


def test_ssh_timeout_is_structured_without_collapsing_into_remote_exit() -> None:
    profile = EnvironmentSSHServerConnectionFactory(OS_ROUTE, ssh_executable="ssh-test").from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
            "RP_SERVER_SEM_UBUNTU_SSH_COMMAND_TIMEOUT_SECONDS": "0.5",
        },
    ).profile
    timeout = subprocess.TimeoutExpired(("ssh-test",), 0.5, output=b"partial", stderr=b"waiting")
    with patch("research_platform.runtime.server.identity.providers.ssh.subprocess.run", side_effect=timeout):
        result = SSHServerConnection(profile, operating_system=OS_ROUTE).execute("hostname")
    assert not result.succeeded
    assert result.failure_kind == ServerTransportFailureKind.TIMEOUT
    assert result.return_code == 124
    assert "timeout" in result.stderr


def test_ssh_process_spawn_failure_is_distinct_from_remote_exit() -> None:
    profile = EnvironmentSSHServerConnectionFactory(OS_ROUTE, ssh_executable="/missing/ssh").from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
        },
    ).profile
    with patch(
        "research_platform.runtime.server.identity.providers.ssh.subprocess.run",
        side_effect=OSError("executable missing"),
    ):
        result = SSHServerConnection(profile, operating_system=OS_ROUTE).execute("hostname")
    assert not result.succeeded
    assert result.failure_kind == ServerTransportFailureKind.SPAWN_ERROR
    assert result.return_code == 127


def test_ssh_exit_255_is_split_into_authentication_and_network_classes() -> None:
    profile = EnvironmentSSHServerConnectionFactory(OS_ROUTE, ssh_executable="ssh-test").from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
        },
    ).profile
    auth_failure = subprocess.CompletedProcess(
        ("ssh-test",), 255, b"", b"Permission denied (publickey,password).\n"
    )
    with patch(
        "research_platform.runtime.server.identity.providers.ssh.subprocess.run",
        return_value=auth_failure,
    ):
        result = SSHServerConnection(profile, operating_system=OS_ROUTE).execute("hostname")
    assert result.failure_kind == ServerTransportFailureKind.AUTHENTICATION

    network_failure = subprocess.CompletedProcess(
        ("ssh-test",), 255, b"", b"ssh: connect to host research.example port 60320: Connection refused\n"
    )
    with patch(
        "research_platform.runtime.server.identity.providers.ssh.subprocess.run",
        return_value=network_failure,
    ):
        result = SSHServerConnection(profile, operating_system=OS_ROUTE).execute("hostname")
    assert result.failure_kind == ServerTransportFailureKind.NETWORK
