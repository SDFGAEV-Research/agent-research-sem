from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import posixpath
import shutil
import subprocess

from research_platform.runtime.host.api import OperatingSystemRoute

from ..api import (
    ServerCommandResult,
    ServerConnectionProfile,
    ServerFileTransferPort,
    ServerFileTransferResult,
    ServerIdentityConfigurationError,
    ServerConnectionPort,
    server_environment_prefix,
)


def _profile_from_environment(
    server_id: str,
    values: Mapping[str, str],
    *,
    ssh_executable: str | None,
) -> ServerConnectionProfile:
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
    control_path_text = values.get(f"{prefix}_SSH_CONTROL_PATH", "").strip()
    control_persist_text = values.get(f"{prefix}_SSH_CONTROL_PERSIST_SECONDS", "600").strip() or "600"
    try:
        control_persist_seconds = int(control_persist_text)
    except ValueError as exc:
        raise ServerIdentityConfigurationError(
            f"{prefix}_SSH_CONTROL_PERSIST_SECONDS must be an integer"
        ) from exc
    selected_executable = ssh_executable or values.get(
        f"{prefix}_SSH", ""
    ).strip() or shutil.which("ssh") or "ssh"
    return ServerConnectionProfile(
        server_id=server_id,
        host=required("HOST"),
        port=port,
        username=required("USER"),
        key_path=Path(key_text) if key_text else None,
        known_hosts_path=Path(known_hosts_text) if known_hosts_text else None,
        ssh_config_path=Path(ssh_config_text) if ssh_config_text else None,
        ssh_executable=selected_executable,
        control_path=(Path(control_path_text).expanduser() if control_path_text else None),
        control_persist_seconds=control_persist_seconds,
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
        if self._profile.control_path is not None:
            argv.extend(
                (
                    "-o",
                    "ControlMaster=auto",
                    "-o",
                    f"ControlPersist={self._profile.control_persist_seconds}",
                    "-o",
                    f"ControlPath={self._profile.control_path}",
                )
            )
        argv.extend((self._profile.destination, command))
        return tuple(argv)

    def _prepare_control_path(self) -> None:
        control_path = self._profile.control_path
        if control_path is not None:
            control_path.parent.mkdir(parents=True, exist_ok=True)

    def execute(self, command: str, *, interactive: bool = False) -> ServerCommandResult:
        if not command.strip():
            raise ValueError("remote command must be non-empty")
        argv = self._argv(command, interactive=interactive)
        runner = self._runner
        if runner is None:
            self._prepare_control_path()
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

    def interactive_argv(
        self,
        command: str,
        *,
        allocate_tty: bool = False,
    ) -> tuple[str, ...]:
        """Return the exact TTY argv for an operator attach operation.

        Command execution remains the normal structured port. This narrow
        projection exists only for an explicitly interactive operator session;
        it never embeds a password or shell secret.
        """

        if not command.strip():
            raise ValueError("interactive remote command must be non-empty")
        argv = list(self._argv(command, interactive=True))
        if allocate_tty:
            argv[1:1] = ["-tt"]
        return tuple(argv)


class SSHServerFileTransfer(ServerFileTransferPort):
    """OpenSSH scp provider with explicit local and remote file identities."""

    def __init__(
        self,
        profile: ServerConnectionProfile,
        *,
        operating_system: OperatingSystemRoute,
        scp_executable: str = "scp",
        runner: object | None = None,
    ) -> None:
        if not scp_executable.strip():
            raise ValueError("scp executable must be non-empty")
        self._profile = profile
        self._operating_system = operating_system
        self._scp_executable = scp_executable
        self._runner = runner

    @property
    def profile(self) -> ServerConnectionProfile:
        return self._profile

    def _argv(self, local_path: Path, remote_path: str, *, interactive: bool) -> tuple[str, ...]:
        argv = [
            self._scp_executable,
            "-P",
            str(self._profile.port),
            "-o",
            f"ConnectTimeout={self._profile.connect_timeout_seconds}",
        ]
        if not interactive:
            argv.append("-B")
        if self._profile.key_path is not None:
            argv.extend(("-i", str(self._profile.key_path)))
        if self._profile.ssh_config_path is not None:
            argv.extend(("-F", str(self._profile.ssh_config_path)))
        if self._profile.known_hosts_path is not None:
            argv.extend(("-o", f"UserKnownHostsFile={self._profile.known_hosts_path}"))
        if self._profile.control_path is not None:
            argv.extend(
                (
                    "-o",
                    "ControlMaster=auto",
                    "-o",
                    f"ControlPersist={self._profile.control_persist_seconds}",
                    "-o",
                    f"ControlPath={self._profile.control_path}",
                )
            )
        argv.extend((str(local_path), f"{self._profile.destination}:{remote_path}"))
        return tuple(argv)

    def upload(
        self,
        local_path: str,
        remote_path: str,
        *,
        interactive: bool = False,
    ) -> ServerFileTransferResult:
        local = Path(local_path).expanduser().resolve(strict=True)
        if not local.is_file():
            raise ValueError("SSH upload local_path must be a regular file")
        remote = str(remote_path)
        if not posixpath.isabs(remote):
            raise ValueError("SSH upload remote_path must be an absolute POSIX target path")
        argv = self._argv(local, remote, interactive=interactive)
        runner = self._runner
        if runner is None:
            if self._profile.control_path is not None:
                self._profile.control_path.parent.mkdir(parents=True, exist_ok=True)
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
            return ServerFileTransferResult(
                self._profile.server_id,
                str(local),
                remote,
                completed.returncode,
                completed.stdout or "",
                completed.stderr or "",
            )
        completed = runner(argv, interactive=interactive)
        if not isinstance(completed, ServerFileTransferResult):
            raise TypeError("injected SCP runner must return ServerFileTransferResult")
        return completed

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
        profile = _profile_from_environment(
            server_id,
            values,
            ssh_executable=self._ssh_executable,
        )
        return SSHServerConnection(profile, operating_system=self._operating_system)


class EnvironmentSSHServerFileTransferFactory:
    """Materialize the same non-secret server identity for scp transfers."""

    def __init__(
        self,
        operating_system: OperatingSystemRoute,
        *,
        scp_executable: str | None = None,
    ) -> None:
        self._operating_system = operating_system
        self._scp_executable = scp_executable

    def from_environment(
        self,
        server_id: str,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> SSHServerFileTransfer:
        values = os.environ if environ is None else environ
        profile = _profile_from_environment(
            server_id,
            values,
            ssh_executable=None,
        )
        scp_executable = self._scp_executable or values.get(
            f"{server_environment_prefix(server_id)}_SCP", ""
        ).strip() or shutil.which("scp") or "scp"
        return SSHServerFileTransfer(
            profile,
            operating_system=self._operating_system,
            scp_executable=scp_executable,
        )


__all__ = [
    "EnvironmentSSHServerConnectionFactory",
    "EnvironmentSSHServerFileTransferFactory",
    "SSHServerConnection",
    "SSHServerFileTransfer",
]
