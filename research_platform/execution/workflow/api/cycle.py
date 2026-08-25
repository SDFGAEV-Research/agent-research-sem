from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import ExecutionContext, JsonValue, OperationResult


@dataclass(frozen=True, slots=True)
class ScientificCycleExecution:
    context_text: str
    primary_result: object
    final_context: ExecutionContext
    operation_results: tuple[OperationResult[JsonValue], ...]


__all__ = ["ScientificCycleExecution"]
