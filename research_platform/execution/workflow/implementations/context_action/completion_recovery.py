from __future__ import annotations

from dataclasses import dataclass

from research_platform.environment.runtime.api import ActionResult
from research_platform.platform.kernel import ExecutionContext, OperationResult
from research_platform.participant.method.api import MethodTaskCompletionReceipt


@dataclass(frozen=True, slots=True)
class CommittedCycleRecovery:
    """Recovery result when Method authority proves task completion already committed."""

    action_result: ActionResult
    completion_receipt: MethodTaskCompletionReceipt
    final_context: ExecutionContext
    operation_results: tuple[OperationResult[object], ...]


__all__ = ["CommittedCycleRecovery"]
