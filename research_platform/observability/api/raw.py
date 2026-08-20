from __future__ import annotations

from typing import Mapping, Protocol

from research_platform.platform.kernel import ExecutionContext


class ContextRawObservationSink(Protocol):
    """Backend-neutral append surface for raw observations bound to an execution context."""

    def append(
        self,
        context: ExecutionContext,
        family: str,
        payload: Mapping[str, object],
        *,
        timestamp: float | None = None,
    ) -> object: ...


__all__ = ["ContextRawObservationSink"]
