from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import posixpath
import shutil
import subprocess
import time
from uuid import uuid4

from research_platform.runtime.host.api import OperatingSystemRoute
from research_platform.platform.kernel.durability.durable_file import durable_replace_file
from research_platform.runtime.server.api import ServerOperationEffect

from ..api import (
    ServerCommandResult,
    ServerConnectionProfile,
    ServerFileTransferPort,
    ServerFileTransferResult,
    ServerIdentityConfigurationError,
    ServerTransportFailureKind,
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
    def optional_local_file(name: str) -> Path | None:
        raw = values.get(f"{prefix}_{name}", "").strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise ServerIdentityConfigurationError(
                f"{prefix}_{name} must be an absolute local path"
            )
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_file():
                raise OSError("not a regular file")
            # Readability is checked at composition time so a Windows ACL or
            # stale mounted path is reported as a local identity defect rather
            # than being misclassified as a remote authentication failure.
            with resolved.open("rb"):
                pass
        except OSError as exc:
            raise ServerIdentityConfigurationError(
                f"{prefix}_{name} must be a readable regular local file"
            ) from exc
        return resolved

    key_path = optional_local_file("KEY_PATH")
    known_hosts_path = optional_local_file("KNOWN_HOSTS")
    ssh_config_path = optional_local_file("SSH_CONFIG")
    control_path_text = values.get(f"{prefix}_SSH_CONTROL_PATH", "").strip()
    control_persist_text = values.get(f"{prefix}_SSH_CONTROL_PERSIST_SECONDS", "600").strip() or "600"
    try:
        control_persist_seconds = int(control_persist_text)
    except ValueError as exc:
        raise ServerIdentityConfigurationError(
            f"{prefix}_SSH_CONTROL_PERSIST_SECONDS must be an integer"
        ) from exc
    timeout_text = values.get(f"{prefix}_SSH_COMMAND_TIMEOUT_SECONDS", "120").strip() or "120"
    transfer_timeout_text = values.get(f"{prefix}_SSH_TRANSFER_TIMEOUT_SECONDS", "1800").strip() or "1800"
    repository_timeout_text = values.get(f"{prefix}_SSH_REPOSITORY_TIMEOUT_SECONDS", "1800").strip() or "1800"
    output_limit_text = values.get(f"{prefix}_SSH_OUTPUT_LIMIT_BYTES", str(8 * 1024 * 1024)).strip() or str(8 * 1024 * 1024)
    try:
        command_timeout_seconds = float(timeout_text)
        transfer_timeout_seconds = float(transfer_timeout_text)
        repository_timeout_seconds = float(repository_timeout_text)
        output_limit_bytes = int(output_limit_text)
    except ValueError as exc:
        raise ServerIdentityConfigurationError(
            f"{prefix}_SSH_COMMAND_TIMEOUT_SECONDS, {prefix}_SSH_TRANSFER_TIMEOUT_SECONDS, "
            f"{prefix}_SSH_REPOSITORY_TIMEOUT_SECONDS and "
            f"{prefix}_SSH_OUTPUT_LIMIT_BYTES must be numeric"
        ) from exc
    selected_executable = ssh_executable or values.get(
        f"{prefix}_SSH", ""
    ).strip() or shutil.which("ssh") or "ssh"
    return ServerConnectionProfile(
        server_id=server_id,
        host=required("HOST"),
        port=port,
        username=required("USER"),
        key_path=key_path,
        known_hosts_path=known_hosts_path,
        ssh_config_path=ssh_config_path,
        ssh_executable=selected_executable,
        control_path=(Path(control_path_text).expanduser() if control_path_text else None),
        control_persist_seconds=control_persist_seconds,
        command_timeout_seconds=command_timeout_seconds,
        transfer_timeout_seconds=transfer_timeout_seconds,
        repository_timeout_seconds=repository_timeout_seconds,
        output_limit_bytes=output_limit_bytes,
    )


def _text_and_size(value: str | bytes | None, *, limit: int) -> tuple[str, int]:
    if value is None:
        return "", 0
    raw = value if isinstance(value, bytes) else value.encode("utf-8", errors="replace")
    size = len(raw)
    if size <= limit:
        return raw.decode("utf-8", errors="replace"), size
    marker = f"\n[output truncated after {limit} bytes]\n".encode("utf-8")
    bounded = raw[: max(0, limit - len(marker))] + marker
    return bounded.decode("utf-8", errors="replace"), size


def _failure_kind(return_code: int, stderr: str) -> ServerTransportFailureKind:
    if return_code == 0:
        return ServerTransportFailureKind.NONE
    lowered = stderr.lower()
    if return_code == 255:
        # OpenSSH can report a transport failure as "Permission denied" while
        # it is still exchanging the server banner (Windows has emitted this
        # as ``Connection to UNKNOWN port -1``). The connection has not
        # reached SSH authentication in that case; classify it as network so
        # operators do not retry credentials for a route failure.
        if "banner exchange:" in lowered or "connection to unknown port" in lowered:
            return ServerTransportFailureKind.NETWORK
        if any(
            marker in lowered
            for marker in (
                "permission denied",
                "authentication that can continue",
                "too many authentication failures",
                "no supported authentication methods",
            )
        ):
            return ServerTransportFailureKind.AUTHENTICATION
        return ServerTransportFailureKind.NETWORK
    return ServerTransportFailureKind.REMOTE_EXIT


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
            "-o",
            "ConnectionAttempts=1",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
        ]
        if not interactive:
            argv.extend(
                (
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "PasswordAuthentication=no",
                    "-o",
                    "KbdInteractiveAuthentication=no",
                    "-o",
                    "NumberOfPasswordPrompts=0",
                    "-o",
                    "StrictHostKeyChecking=yes",
                )
            )
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

    def execute(
        self,
        command: str,
        *,
        interactive: bool = False,
        effect: ServerOperationEffect = ServerOperationEffect.UNKNOWN,
        timeout_seconds: float | None = None,
    ) -> ServerCommandResult:
        del effect
        if not command.strip():
            raise ValueError("remote command must be non-empty")
        argv = self._argv(command, interactive=interactive)
        effective_timeout = (
            self._profile.command_timeout_seconds
            if timeout_seconds is None
            else float(timeout_seconds)
        )
        if effective_timeout <= 0:
            raise ValueError("SSH command timeout must be positive")
        if interactive:
            # Interactive mode is an explicit operator action. Requesting a
            # TTY is required for password and host-key prompts; without it,
            # OpenSSH reports an authentication failure from a pipe.
            argv = (argv[0], "-tt", *argv[1:])
        runner = self._runner
        if runner is None:
            self._prepare_control_path()
            started = time.perf_counter()
            try:
                completed = subprocess.run(
                    argv,
                    check=False,
                    capture_output=True,
                    text=False,
                    stdin=None if interactive else subprocess.DEVNULL,
                    timeout=effective_timeout,
                    creationflags=(
                        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                        if self._operating_system.is_windows
                        else 0
                    ),
                )
                stdout, stdout_bytes = _text_and_size(
                    completed.stdout, limit=self._profile.output_limit_bytes
                )
                stderr, stderr_bytes = _text_and_size(
                    completed.stderr, limit=self._profile.output_limit_bytes
                )
                failure_kind = _failure_kind(completed.returncode, stderr)
                return_code = completed.returncode
            except subprocess.TimeoutExpired as exc:
                stdout, stdout_bytes = _text_and_size(
                    exc.stdout, limit=self._profile.output_limit_bytes
                )
                stderr, stderr_bytes = _text_and_size(
                    exc.stderr, limit=self._profile.output_limit_bytes
                )
                stderr = (stderr + "\n" if stderr else "") + (
                    f"SSH command exceeded {effective_timeout:g}s timeout"
                )
                stderr_bytes = len(stderr.encode("utf-8", errors="replace"))
                failure_kind = ServerTransportFailureKind.TIMEOUT
                return_code = 124
            except OSError as exc:
                stdout, stdout_bytes = "", 0
                stderr = f"{type(exc).__name__}: {exc}"
                stderr_bytes = len(stderr.encode("utf-8", errors="replace"))
                failure_kind = ServerTransportFailureKind.SPAWN_ERROR
                return_code = 127
            duration_seconds = time.perf_counter() - started
            return ServerCommandResult(
                self._profile.server_id,
                command,
                return_code,
                stdout,
                stderr,
                failure_kind,
                duration_seconds,
                stdout_bytes,
                stderr_bytes,
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

    def run_interactive(self, argv: tuple[str, ...]) -> int:
        """Run an already materialized SSH TTY argv under identity ownership."""

        if not argv or argv[0] != self._profile.ssh_executable:
            raise ValueError("interactive SSH argv was not produced by this server identity")
        completed = subprocess.run(
            argv,
            check=False,
            stdin=None,
            creationflags=(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                if self._operating_system.is_windows
                else 0
            ),
        )
        return completed.returncode


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

    @property
    def executable(self) -> str:
        return self._scp_executable

    def _argv(self, local_path: Path, remote_path: str, *, interactive: bool) -> tuple[str, ...]:
        argv = [
            self._scp_executable,
            "-P",
            str(self._profile.port),
            "-o",
            f"ConnectTimeout={self._profile.connect_timeout_seconds}",
            "-o",
            "ConnectionAttempts=1",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
        ]
        if not interactive:
            argv.extend(
                (
                    "-B",
                    "-o",
                    "PasswordAuthentication=no",
                    "-o",
                    "KbdInteractiveAuthentication=no",
                    "-o",
                    "NumberOfPasswordPrompts=0",
                    "-o",
                    "StrictHostKeyChecking=yes",
                )
            )
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

    def _download_argv(self, remote_path: str, local_path: Path, *, interactive: bool) -> tuple[str, ...]:
        argv = [
            self._scp_executable,
            "-P",
            str(self._profile.port),
            "-o",
            f"ConnectTimeout={self._profile.connect_timeout_seconds}",
            "-o",
            "ConnectionAttempts=1",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
        ]
        if not interactive:
            argv.extend(
                (
                    "-B",
                    "-o",
                    "PasswordAuthentication=no",
                    "-o",
                    "KbdInteractiveAuthentication=no",
                    "-o",
                    "NumberOfPasswordPrompts=0",
                    "-o",
                    "StrictHostKeyChecking=yes",
                )
            )
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
        argv.extend((f"{self._profile.destination}:{remote_path}", str(local_path)))
        return tuple(argv)

    @staticmethod
    def _validate_remote_path(remote_path: str) -> str:
        remote = str(remote_path)
        if not posixpath.isabs(remote) or any(char in remote for char in "\x00\r\n"):
            raise ValueError("SSH remote_path must be an absolute POSIX path without control characters")
        return remote

    def _run_transfer(
        self,
        argv: tuple[str, ...],
        *,
        local_path: str,
        remote_path: str,
        interactive: bool,
    ) -> ServerFileTransferResult:
        if self._profile.control_path is not None:
            self._profile.control_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=False,
                stdin=None if interactive else subprocess.DEVNULL,
                timeout=self._profile.transfer_timeout_seconds,
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    if self._operating_system.is_windows
                    else 0
                ),
            )
            stdout, stdout_bytes = _text_and_size(
                completed.stdout, limit=self._profile.output_limit_bytes
            )
            stderr, stderr_bytes = _text_and_size(
                completed.stderr, limit=self._profile.output_limit_bytes
            )
            failure_kind = _failure_kind(completed.returncode, stderr)
            return_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stdout_bytes = _text_and_size(
                exc.stdout, limit=self._profile.output_limit_bytes
            )
            stderr, stderr_bytes = _text_and_size(
                exc.stderr, limit=self._profile.output_limit_bytes
            )
            stderr = (stderr + "\n" if stderr else "") + (
                f"SCP transfer exceeded {self._profile.transfer_timeout_seconds:g}s timeout"
            )
            stderr_bytes = len(stderr.encode("utf-8", errors="replace"))
            failure_kind = ServerTransportFailureKind.TIMEOUT
            return_code = 124
        except OSError as exc:
            stdout, stdout_bytes = "", 0
            stderr = f"{type(exc).__name__}: {exc}"
            stderr_bytes = len(stderr.encode("utf-8", errors="replace"))
            failure_kind = ServerTransportFailureKind.SPAWN_ERROR
            return_code = 127
        return ServerFileTransferResult(
            self._profile.server_id,
            local_path,
            remote_path,
            return_code,
            stdout,
            stderr,
            failure_kind,
            time.perf_counter() - started,
            stdout_bytes,
            stderr_bytes,
        )

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
        remote = self._validate_remote_path(remote_path)
        argv = self._argv(local, remote, interactive=interactive)
        runner = self._runner
        if runner is None:
            return self._run_transfer(
                argv,
                local_path=str(local),
                remote_path=remote,
                interactive=interactive,
            )
        completed = runner(argv, interactive=interactive)
        if not isinstance(completed, ServerFileTransferResult):
            raise TypeError("injected SCP runner must return ServerFileTransferResult")
        return completed

    def download(
        self,
        remote_path: str,
        local_path: str,
        *,
        interactive: bool = False,
    ) -> ServerFileTransferResult:
        remote = self._validate_remote_path(remote_path)
        local = Path(local_path).expanduser()
        if not local.is_absolute():
            raise ValueError("SSH download local_path must be an absolute local target path")
        if any(char in str(local) for char in "\x00\r\n"):
            raise ValueError("SSH download local_path contains control characters")
        if local.exists() and local.is_dir():
            raise ValueError("SSH download local_path must be a file target, not a directory")
        if not local.parent.is_dir():
            raise ValueError("SSH download local_path parent directory must exist")
        # Never let scp write directly into an authoritative artifact.  A
        # timeout or process interruption may leave a valid-looking partial
        # file behind; the target is replaced only after the transfer has
        # completed successfully and the temporary file exists.
        temporary = local.with_name(f".{local.name}.{uuid4().hex}.part")
        argv = self._download_argv(remote, temporary, interactive=interactive)
        try:
            if self._runner is None:
                result = self._run_transfer(
                    argv,
                    local_path=str(temporary),
                    remote_path=remote,
                    interactive=interactive,
                )
            else:
                result = self._runner(argv, interactive=interactive)
                if not isinstance(result, ServerFileTransferResult):
                    raise TypeError("injected SCP runner must return ServerFileTransferResult")
            if not result.succeeded:
                return ServerFileTransferResult(
                    self._profile.server_id,
                    str(local),
                    remote,
                    result.return_code,
                    result.stdout,
                    result.stderr,
                    result.failure_kind,
                    result.duration_seconds,
                    result.stdout_bytes,
                    result.stderr_bytes,
                )
            if not temporary.is_file():
                raise RuntimeError("SCP reported success but its temporary download is missing")
            durable_replace_file(temporary, local)
            return ServerFileTransferResult(
                self._profile.server_id,
                str(local),
                remote,
                result.return_code,
                result.stdout,
                result.stderr,
                result.failure_kind,
                result.duration_seconds,
                result.stdout_bytes,
                result.stderr_bytes,
            )
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

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
