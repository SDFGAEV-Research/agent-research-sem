from __future__ import annotations

from typing import Protocol, runtime_checkable

from research_platform.platform.kernel import ExecutionContext


@runtime_checkable
class ContextMetricSink(Protocol):
    def observe(
        self,
        context: ExecutionContext,
        name: str,
        value: float,
        **dimensions: str,
    ) -> object: ...
