from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from .contracts import ServerCommandResult, ServerConnectionProfile, ServerHealthReport


class ServerConnectionPort(Protocol):
    @property
    def profile(self) -> ServerConnectionProfile: ...

    def execute(self, command: str, *, interactive: bool = False) -> ServerCommandResult: ...

    def health(self, *, interactive: bool = False) -> ServerHealthReport: ...


class ServerConnectionFactoryPort(Protocol):
    def from_environment(
        self,
        server_id: str,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> ServerConnectionPort: ...


__all__ = ["ServerConnectionFactoryPort", "ServerConnectionPort"]
