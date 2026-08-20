from __future__ import annotations

from typing import Protocol

from .serving import MemoryReadSnapshot, MemoryServingService
from .deluxe.api.ports import DeluxeServingSource, DeluxeReadSnapshot
from .session_state_api import SEMSessionStatePort


class ServingSessionSource(Protocol):
    """Pinned read source exposed to scientific serving providers."""

    def open_snapshot(self) -> MemoryReadSnapshot: ...


class SessionServingFactory(Protocol):
    def __call__(self, source: ServingSessionSource) -> MemoryServingService: ...


class DeluxeServingSessionSource(ServingSessionSource, Protocol):
    """Session source for an explicit Deluxe treatment."""

    def open_deluxe_snapshot(self) -> DeluxeReadSnapshot: ...


class DeluxeSnapshotFactory(Protocol):
    def __call__(self, state: SEMSessionStatePort) -> DeluxeServingSource: ...


class DeluxeSessionServingFactory(Protocol):
    def __call__(self, source: DeluxeServingSessionSource): ...


__all__ = [
    "DeluxeSessionServingFactory",
    "DeluxeServingSessionSource",
    "DeluxeSnapshotFactory",
    "ServingSessionSource",
    "SessionServingFactory",
]
