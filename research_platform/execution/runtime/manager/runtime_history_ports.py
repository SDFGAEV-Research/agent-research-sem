from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol

from .runtime_history_contracts import RuntimeHistoryEntry, RuntimeHistoryProjectionKind


class RuntimeHistoryAppendSession(Protocol):
    """One verified, exclusively-held append opportunity against a fixed history tail."""

    @property
    def tail(self) -> dict[str, object] | None: ...

    def append(
        self,
        state: object,
        *,
        projection_kind: RuntimeHistoryProjectionKind = RuntimeHistoryProjectionKind.STATE_WRITE,
    ) -> RuntimeHistoryEntry: ...


class RuntimeHistoryReadPort(Protocol):
    """Read-only integrity/projection boundary for runtime history."""

    def verify(self) -> tuple[str, ...]: ...

    def assert_tail_matches(self, state: object) -> None: ...

    def reference(self) -> str: ...


class RuntimeHistoryPort(RuntimeHistoryReadPort, Protocol):
    """Mutable runtime-history semantic boundary used by the control transaction."""

    def assert_integrity(self) -> None: ...

    def verified_append_session(self) -> AbstractContextManager[RuntimeHistoryAppendSession]: ...

    def append(
        self,
        state: object,
        *,
        projection_kind: RuntimeHistoryProjectionKind = RuntimeHistoryProjectionKind.STATE_WRITE,
    ) -> RuntimeHistoryEntry: ...

    def reconcile_authoritative(self, state: object) -> bool: ...


class RuntimeHistoryStoragePort(Protocol):
    """Opaque durable row storage. It owns no hash-chain or reconciliation semantics."""

    def lines(self) -> tuple[str, ...]: ...

    def append(self, encoded_row: bytes) -> None: ...

    def reference(self) -> str: ...

    def exclusive(self) -> AbstractContextManager[object]: ...


__all__ = [
    "RuntimeHistoryAppendSession",
    "RuntimeHistoryPort",
    "RuntimeHistoryReadPort",
    "RuntimeHistoryStoragePort",
]
