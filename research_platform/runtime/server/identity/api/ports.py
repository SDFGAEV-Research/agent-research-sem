from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from .contracts import ServerCommandResult, ServerConnectionProfile, ServerFileTransferResult


class ServerConnectionPort(Protocol):
    @property
    def profile(self) -> ServerConnectionProfile: ...

    def execute(self, command: str, *, interactive: bool = False) -> ServerCommandResult: ...

    def interactive_argv(self, command: str) -> tuple[str, ...]: ...


class ServerConnectionFactoryPort(Protocol):
    def from_environment(
        self,
        server_id: str,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> ServerConnectionPort: ...


class ServerFileTransferPort(Protocol):
    @property
    def profile(self) -> ServerConnectionProfile: ...

    def upload(
        self,
        local_path: str,
        remote_path: str,
        *,
        interactive: bool = False,
    ) -> ServerFileTransferResult: ...


class ServerFileTransferFactoryPort(Protocol):
    def from_environment(
        self,
        server_id: str,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> ServerFileTransferPort: ...


__all__ = [
    "ServerConnectionFactoryPort",
    "ServerConnectionPort",
    "ServerFileTransferFactoryPort",
    "ServerFileTransferPort",
]
