from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import ExecutionContext, OperationResult


@dataclass(frozen=True, slots=True)
class ScientificCycleExecution:
    context_text: str
    primary_result: object
    final_context: ExecutionContext
    operation_results: tuple[OperationResult[object], ...]


__all__ = ["ScientificCycleExecution"]
