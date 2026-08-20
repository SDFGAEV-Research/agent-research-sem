from __future__ import annotations

from typing import Protocol

from .serving import MemoryReadSnapshot, MemoryServingService


class ServingSessionSource(Protocol):
    """Pinned read source exposed to scientific serving providers."""

    def open_snapshot(self) -> MemoryReadSnapshot: ...


class SessionServingFactory(Protocol):
    def __call__(self, source: ServingSessionSource) -> MemoryServingService: ...


__all__ = ["ServingSessionSource", "SessionServingFactory"]
