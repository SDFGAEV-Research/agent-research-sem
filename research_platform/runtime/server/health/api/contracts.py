from __future__ import annotations

from dataclasses import dataclass
import posixpath


def _absolute(value: str, field: str) -> str:
    if not posixpath.isabs(value) or posixpath.normpath(value) == "/":
        raise ValueError(f"{field} must be an absolute non-root POSIX path")
    return posixpath.normpath(value)


@dataclass(frozen=True, slots=True)
class ServerRuntimeHealthSpec:
    """Exact remote paths and identities required by one platform deployment."""

    platform_root: str
    release_root: str
    python_executable: str
    node_executable: str
    java_executable: str
    platform_management_executable: str
    tmux_executable: str
    sha256sum_executable: str
    tmux_binary_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "platform_root",
            "release_root",
            "python_executable",
            "node_executable",
            "java_executable",
            "platform_management_executable",
            "tmux_executable",
            "sha256sum_executable",
        ):
            _absolute(getattr(self, name), name)
        if len(self.tmux_binary_sha256) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in self.tmux_binary_sha256
        ):
            raise ValueError("tmux_binary_sha256 must be a SHA-256 hex digest")

from research_platform.runtime.server.identity.api import ServerCommandResult


@dataclass(frozen=True, slots=True)
class ServerHealthReport:
    """A read-only health projection derived from one server command result."""

    server_id: str
    reachable: bool
    host_name: str | None
    python_version: str | None
    git_version: str | None
    tmux_version: str | None
    raw: ServerCommandResult
    platform_ready: bool = False
    checks: tuple[tuple[str, str], ...] = ()
    issues: tuple[str, ...] = ()


__all__ = ["ServerHealthReport", "ServerRuntimeHealthSpec"]
