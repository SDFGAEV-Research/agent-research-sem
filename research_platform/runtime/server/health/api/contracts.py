from __future__ import annotations

from dataclasses import dataclass

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


__all__ = ["ServerHealthReport"]
