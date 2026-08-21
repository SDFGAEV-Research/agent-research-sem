from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import shutil
import subprocess

from research_platform.runtime.host.api import OperatingSystemRoute

from ..api import (
    ServerAuthenticationUnavailable,
    ServerCommandResult,
    ServerConnectionProfile,
    ServerHealthReport,
    ServerIdentityConfigurationError,
    ServerConnectionPort,
    server_environment_prefix,
)


class SSHServerConnection(ServerConnectionPort):
    """OpenSSH provider with no local shell and no secret in argv."""

    def __init__(
        self,
        profile: ServerConnectionProfile,
        *,
        operating_system: OperatingSystemRoute,
        runner: object | None = None,
    ) -> None:
        self._profile = profile
        self._operating_system = operating_system
        self._runner = runner

    @property
    def profile(self) -> ServerConnectionProfile:
        return self._profile

    def _argv(self, command: str, *, interactive: bool) -> tuple[str, ...]:
        argv = [
            self._profile.ssh_executable,
            "-p",
            str(self._profile.port),
            "-o",
            f"ConnectTimeout={self._profile.connect_timeout_seconds}",
        ]
        if not interactive:
            argv.extend(("-o", "BatchMode=yes"))
        if self._profile.key_path is not None:
            argv.extend(("-i", str(self._profile.key_path)))
        if self._profile.ssh_config_path is not None:
            argv.extend(("-F", str(self._profile.ssh_config_path)))
        if self._profile.known_hosts_path is not None:
            argv.extend(("-o", f"UserKnownHostsFile={self._profile.known_hosts_path}"))
        argv.extend((self._profile.destination, command))
        return tuple(argv)

    def execute(self, command: str, *, interactive: bool = False) -> ServerCommandResult:
        if not command.strip():
            raise ValueError("remote command must be non-empty")
        argv = self._argv(command, interactive=interactive)
        runner = self._runner
        if runner is None:
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                stdin=None if interactive else subprocess.DEVNULL,
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    if self._operating_system.is_windows
                    else 0
                ),
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            return ServerCommandResult(
                self._profile.server_id,
                command,
                completed.returncode,
                stdout,
                stderr,
            )
        completed = runner(argv, interactive=interactive)
        if not isinstance(completed, ServerCommandResult):
            raise TypeError("injected SSH runner must return ServerCommandResult")
        return completed

    def health(self, *, interactive: bool = False) -> ServerHealthReport:
        command = (
            "printf 'host='; hostname; "
            "printf 'python='; python3 --version 2>&1; "
            "printf 'git='; git --version 2>&1; "
            "printf 'tmux='; tmux -V 2>&1; "
            "printf 'disk='; df -h / /data 2>&1"
        )
        result = self.execute(command, interactive=interactive)
        values: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
        return ServerHealthReport(
            server_id=self._profile.server_id,
            reachable=result.return_code == 0,
            host_name=values.get("host"),
            python_version=values.get("python"),
            git_version=values.get("git"),
            tmux_version=values.get("tmux"),
            raw=result,
        )


class EnvironmentSSHServerConnectionFactory:
    """Materializes one server profile from environment-owned configuration."""

    def __init__(
        self,
        operating_system: OperatingSystemRoute,
        *,
        ssh_executable: str | None = None,
    ) -> None:
        self._operating_system = operating_system
        self._ssh_executable = ssh_executable

    def from_environment(
        self,
        server_id: str,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> SSHServerConnection:
        values = os.environ if environ is None else environ
        prefix = server_environment_prefix(server_id)

        def required(name: str) -> str:
            value = values.get(f"{prefix}_{name}", "").strip()
            if not value:
                raise ServerIdentityConfigurationError(
                    f"missing environment variable {prefix}_{name}"
                )
            return value

        port_text = required("PORT")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ServerIdentityConfigurationError(
                f"{prefix}_PORT must be an integer"
            ) from exc
        key_text = values.get(f"{prefix}_KEY_PATH", "").strip()
        known_hosts_text = values.get(f"{prefix}_KNOWN_HOSTS", "").strip()
        ssh_config_text = values.get(f"{prefix}_SSH_CONFIG", "").strip()
        ssh_executable = self._ssh_executable or values.get(
            f"{prefix}_SSH", ""
        ).strip() or shutil.which("ssh") or "ssh"
        profile = ServerConnectionProfile(
            server_id=server_id,
            host=required("HOST"),
            port=port,
            username=required("USER"),
            key_path=Path(key_text) if key_text else None,
            known_hosts_path=Path(known_hosts_text) if known_hosts_text else None,
            ssh_config_path=Path(ssh_config_text) if ssh_config_text else None,
            ssh_executable=ssh_executable,
        )
        return SSHServerConnection(profile, operating_system=self._operating_system)


__all__ = ["EnvironmentSSHServerConnectionFactory", "SSHServerConnection"]
