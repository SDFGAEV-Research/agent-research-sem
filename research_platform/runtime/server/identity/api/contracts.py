from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


class ServerIdentityConfigurationError(ValueError):
    """A server profile is incomplete or contains an unsafe value."""


class ServerAuthenticationUnavailable(RuntimeError):
    """The requested non-interactive connection has no usable SSH identity."""


@dataclass(frozen=True, slots=True)
class ServerConnectionProfile:
    """Non-secret connection identity for one managed remote host.

    Values are materialized from the process environment at composition time.
    Passwords are deliberately not represented here: automated runs use an SSH
    key or agent, while an interactive run may let OpenSSH prompt on its TTY.
    """

    server_id: str
    host: str
    port: int
    username: str
    key_path: Path | None = None
    known_hosts_path: Path | None = None
    ssh_config_path: Path | None = None
    ssh_executable: str = "ssh"
    connect_timeout_seconds: int = 15
    control_path: Path | None = None
    control_persist_seconds: int = 600

    def __post_init__(self) -> None:
        if not self.server_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.server_id):
            raise ServerIdentityConfigurationError("server_id must be a safe non-empty identifier")
        if not self.host or any(char.isspace() for char in self.host):
            raise ServerIdentityConfigurationError("server host must be non-empty and contain no whitespace")
        if not 1 <= self.port <= 65535:
            raise ServerIdentityConfigurationError("server port must be in [1, 65535]")
        if not self.username or any(char.isspace() for char in self.username):
            raise ServerIdentityConfigurationError("server username must be non-empty and contain no whitespace")
        if not self.ssh_executable:
            raise ServerIdentityConfigurationError("ssh executable must be non-empty")
        if self.connect_timeout_seconds <= 0:
            raise ServerIdentityConfigurationError("SSH connect timeout must be positive")
        if self.control_path is not None:
            if not self.control_path.is_absolute():
                raise ServerIdentityConfigurationError("SSH control path must be absolute")
            control_text = str(self.control_path)
            if any(char in control_text for char in "\x00\r\n"):
                raise ServerIdentityConfigurationError("SSH control path contains unsafe characters")
            # OpenSSH Unix-domain control sockets are limited to 108 bytes.
            # Validate the worst-case supported template before any network
            # operation; otherwise a long path is misreported as a remote
            # connectivity failure. ``%C`` is the only dynamic token owned by
            # this platform and expands to a 40-character connection digest.
            dynamic_tokens = control_text.replace("%%", "").replace("%C", "")
            if "%" in dynamic_tokens:
                raise ServerIdentityConfigurationError(
                    "SSH control path may contain only the %C or %% OpenSSH token"
                )
            expanded_length = len(
                control_text.replace("%C", "0" * 40).replace("%%", "%").encode("utf-8")
            )
            if expanded_length >= 108:
                raise ServerIdentityConfigurationError(
                    "SSH control path template expands to 108 or more bytes; use a shorter local path"
                )
        if self.control_persist_seconds <= 0:
            raise ServerIdentityConfigurationError("SSH control persist seconds must be positive")

    @property
    def destination(self) -> str:
        return f"{self.username}@{self.host}"


@dataclass(frozen=True, slots=True)
class ServerCommandResult:
    server_id: str
    command: str
    return_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


@dataclass(frozen=True, slots=True)
class ServerFileTransferResult:
    server_id: str
    local_path: str
    remote_path: str
    return_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


def server_environment_prefix(server_id: str, *, root: str = "RP_SERVER") -> str:
    token = re.sub(r"[^A-Za-z0-9]", "_", server_id).upper()
    if not token or token[0].isdigit():
        token = "S_" + token
    return f"{root}_{token}"


__all__ = [
    "ServerAuthenticationUnavailable",
    "ServerCommandResult",
    "ServerConnectionProfile",
    "ServerFileTransferResult",
    "ServerIdentityConfigurationError",
    "server_environment_prefix",
]
