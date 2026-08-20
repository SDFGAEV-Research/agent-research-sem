from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import OperationResult

from research_platform.execution.decision.cycle_identity import DecisionCycleIdentity


@dataclass(frozen=True, slots=True)
class DecisionCycleResult:
    run_id: str
    decision_cycle_id: str
    context_text: str
    primary_result: object
    operation_results: tuple[OperationResult[object], ...] = ()
    cycle_identity: DecisionCycleIdentity | None = None

