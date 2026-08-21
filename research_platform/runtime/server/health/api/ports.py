from __future__ import annotations

from typing import Protocol

from research_platform.runtime.server.identity.api import ServerConnectionPort

from .contracts import ServerHealthReport, ServerRuntimeHealthSpec


class ServerHealthProbePort(Protocol):
    """Derive health facts from an injected server connection."""

    def probe(
        self,
        connection: ServerConnectionPort,
        *,
        interactive: bool = False,
        specification: ServerRuntimeHealthSpec | None = None,
    ) -> ServerHealthReport: ...


__all__ = ["ServerHealthProbePort"]
