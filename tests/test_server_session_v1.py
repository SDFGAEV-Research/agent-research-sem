from __future__ import annotations

from pathlib import Path

import pytest

from research_platform.runtime.server.identity.api import ServerCommandResult, server_environment_prefix
from research_platform.runtime.server.lifecycle.api import ServerRemoteProfile
from research_platform.runtime.server.lifecycle.providers import (
    SSHRemoteTmuxCommandRunner,
    SSHRemoteTmuxSessionControl,
)


def _environment(root: Path) -> dict[str, str]:
    prefix = server_environment_prefix("sem-ubuntu")
    return {
        f"{prefix}_PLATFORM_ROOT": "/srv/research-platform",
        f"{prefix}_RELEASE_ROOT": "/srv/research-platform/releases",
        f"{prefix}_OPERATOR_CWD": "/srv/research-platform",
        f"{prefix}_OPERATOR_SHELL": "/usr/bin/bash",
        f"{prefix}_REMOTE_ENV": "/usr/bin/env",
        f"{prefix}_SHA256SUM": "/usr/bin/sha256sum",
        f"{prefix}_PYTHON": "/srv/research-platform/envs/sem/bin/python",
        f"{prefix}_NODE": "/srv/research-platform/toolchains/node/bin/node",
        f"{prefix}_JAVA": "/srv/research-platform/toolchains/java/bin/java",
        f"{prefix}_PLATFORM_MANAGE": "/srv/research-platform/envs/sem/bin/research-platform-manage",
        f"{prefix}_TMUX": "/usr/local/bin/tmux",
        f"{prefix}_TMUX_SHA256": "a" * 64,
        f"{prefix}_TMUX_SERVER_LABEL": "research-platform",
        f"{prefix}_TMUX_CONFIG": "/dev/null",
        f"{prefix}_TMUX_SOCKET_DIRECTORY": "/tmp",
        f"{prefix}_SESSION_NAME": "research-platform-shell",
        f"{prefix}_LOCAL_BINDING_ROOT": str(root),
        f"{prefix}_REMOTE_HOME": "/home/ubuntu",
        f"{prefix}_REMOTE_PATH": "/usr/local/bin:/usr/bin:/bin",
    }


def test_remote_profile_requires_explicit_runtime_paths(tmp_path: Path) -> None:
    values = _environment(tmp_path)
    values.pop("RP_SERVER_SEM_UBUNTU_TMUX_SHA256")
    with pytest.raises(ValueError, match="TMUX_SHA256"):
        ServerRemoteProfile.from_environment("sem-ubuntu", environ=values)


def test_remote_profile_materializes_one_non_secret_runtime_identity(tmp_path: Path) -> None:
    profile = ServerRemoteProfile.from_environment(
        "sem-ubuntu", environ=_environment(tmp_path)
    )
    assert profile.platform_root == "/srv/research-platform"
    assert profile.session_environment == (
        ("HOME", "/home/ubuntu"),
        ("LANG", "C.UTF-8"),
        ("LC_ALL", "C"),
        ("PATH", "/usr/local/bin:/usr/bin:/bin"),
    )


def test_remote_tmux_runner_uses_argv_shaped_command_without_local_shell(tmp_path: Path) -> None:
    captured: list[tuple[str, bool]] = []

    class Connection:
        def execute(self, command: str, *, interactive: bool = False) -> ServerCommandResult:
            captured.append((command, interactive))
            return ServerCommandResult("sem-ubuntu", command, 0, "ok\n", "")

    runner = SSHRemoteTmuxCommandRunner(
        Connection(),
        remote_env_executable="/usr/bin/env",
        base_environment={"HOME": "/home/ubuntu", "PATH": "/usr/bin"},
    )
    result = runner.run(("/usr/local/bin/tmux", "-L", "research-platform", "has-session", "-t", "=shell"), environment={"LC_ALL": "C"})
    assert result.returncode == 0
    assert captured[0][0].startswith("/usr/bin/env -i")
    assert "shell" in captured[0][0]
    assert captured[0][1] is False


def test_remote_tmux_control_attests_binary_and_allocates_tty(tmp_path: Path) -> None:
    captured: list[tuple[str, bool]] = []

    class Connection:
        def execute(self, command: str, *, interactive: bool = False) -> ServerCommandResult:
            captured.append((command, interactive))
            if "sha256sum" in command:
                return ServerCommandResult("sem-ubuntu", command, 0, "a" * 64 + "  /usr/local/bin/tmux\n", "")
            return ServerCommandResult("sem-ubuntu", command, 1, "", "missing session")

        def interactive_argv(self, command: str, *, allocate_tty: bool = False) -> tuple[str, ...]:
            return ("ssh", "-tt" if allocate_tty else "-T", command)

    control = SSHRemoteTmuxSessionControl(
        Connection(),
        tmux_executable="/usr/local/bin/tmux",
        binary_identity_digest="a" * 64,
        server_label="research-platform",
        config_file="/dev/null",
        socket_directory="/tmp",
        remote_env_executable="/usr/bin/env",
        sha256sum_executable="/usr/bin/sha256sum",
        session_environment={"HOME": "/home/ubuntu", "PATH": "/usr/bin"},
    )
    assert control.identity_verified
    assert control.attach_argv("research-platform-shell")[1] == "-tt"
