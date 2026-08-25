from __future__ import annotations

from typing import Mapping, Protocol

from research_platform.platform.kernel import ExecutionContext, JsonObject, JsonValue


class ContextRawObservationSink(Protocol):
    """Backend-neutral append surface for raw observations bound to an execution context."""

    def append(
        self,
        context: ExecutionContext,
        family: str,
        payload: JsonObject,
        *,
        timestamp: float | None = None,
    ) -> JsonValue: ...


__all__ = ["ContextRawObservationSink"]
