from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

from research_platform.experimentation.experiment.api import ExperimentWorkloadFailure, FailureScope


@dataclass(frozen=True, slots=True)
class WorkloadDecision:
    """One environment-neutral planner decision.

    The action vocabulary and payload schema belong to the environment adapter;
    the workload system only transports them and records their identity.
    """

    action_type: str
    payload: Mapping[str, object] = field(default_factory=dict)
    rationale: str = ""
    completion_claim: bool = False

    def __post_init__(self) -> None:
        if not self.action_type.strip():
            raise ValueError("workload decision action_type must be non-empty")
        if not isinstance(self.payload, Mapping):
            raise TypeError("workload decision payload must be a mapping")


@dataclass(frozen=True, slots=True)
class WorkloadTaskResult:
    """Generic task receipt shared by MC and non-MC workload adapters."""

    task_id: str
    family: str
    success: bool
    utility: float
    steps: int
    duration_s: float
    lineage_id: str
    failure_reason: str = ""
    memory_queries: int = 0
    planner_actions: tuple[Mapping[str, object], ...] = ()
    decision_cycles: tuple[Mapping[str, object], ...] = ()
    completion_receipt: object | None = None
    blocked: bool = False
    failure_scope: str = FailureScope.TASK.value
    diagnostics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.family.strip() or not self.lineage_id.strip():
            raise ValueError("workload task result identity fields must be non-empty")
        if self.steps < 0 or self.memory_queries < 0:
            raise ValueError("workload task result counts cannot be negative")
        if not self.failure_scope.strip():
            raise ValueError("workload task result failure_scope must be non-empty")


class WorkloadTaskRunError(ExperimentWorkloadFailure):
    """Failure raised by the generic runner with explicit continuation scope."""

    def __init__(
        self,
        phase: str,
        code: str,
        message: str,
        *,
        scope: FailureScope,
    ) -> None:
        super().__init__(phase, code, message, scope=scope)


__all__ = ["WorkloadDecision", "WorkloadTaskResult", "WorkloadTaskRunError"]
