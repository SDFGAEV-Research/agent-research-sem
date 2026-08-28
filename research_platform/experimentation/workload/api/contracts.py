from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
import math
from typing import Protocol

from research_platform.experimentation.experiment.api import ExperimentWorkloadFailure, FailureScope
from research_platform.platform.kernel import JsonValue


class WorkloadCompletionReceipt(Protocol):
    completion_key: str


@dataclass(frozen=True, slots=True)
class WorkloadDecision:
    """One environment-neutral planner decision.

    The action vocabulary and payload schema belong to the environment adapter;
    the workload system only transports them and records their identity.
    """

    action_type: str
    payload: Mapping[str, JsonValue] = field(default_factory=dict)
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
    planner_actions: tuple[Mapping[str, JsonValue], ...] = ()
    decision_cycles: tuple[Mapping[str, JsonValue], ...] = ()
    completion_receipt: WorkloadCompletionReceipt | None = None
    blocked: bool = False
    failure_scope: str = FailureScope.TASK.value
    diagnostics: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("task_id", self.task_id),
            ("family", self.family),
            ("lineage_id", self.lineage_id),
            ("failure_reason", self.failure_reason),
            ("failure_scope", self.failure_scope),
        ):
            if type(value) is not str:
                raise TypeError(f"workload task result {field_name} must be a string")
        if not self.task_id.strip() or not self.family.strip() or not self.lineage_id.strip():
            raise ValueError("workload task result identity fields must be non-empty")
        if type(self.success) is not bool or type(self.blocked) is not bool:
            raise TypeError("workload task result success/blocked must be booleans")
        if type(self.steps) is not int or type(self.memory_queries) is not int:
            raise TypeError("workload task result counts must be integers")
        if self.steps < 0 or self.memory_queries < 0:
            raise ValueError("workload task result counts cannot be negative")
        for field_name, value in (("utility", self.utility), ("duration_s", self.duration_s)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"workload task result {field_name} must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError(f"workload task result {field_name} must be finite")
        if self.duration_s < 0:
            raise ValueError("workload task result duration_s cannot be negative")
        if not self.failure_scope.strip():
            raise ValueError("workload task result failure_scope must be non-empty")
        try:
            FailureScope(self.failure_scope)
        except ValueError as exc:
            raise ValueError("workload task result failure_scope is not declared") from exc
        if any(not isinstance(item, Mapping) for item in self.planner_actions):
            raise TypeError("workload planner_actions must contain mappings")
        if any(not isinstance(item, Mapping) for item in self.decision_cycles):
            raise TypeError("workload decision_cycles must contain mappings")
        if not isinstance(self.diagnostics, Mapping):
            raise TypeError("workload diagnostics must be a mapping")


@dataclass(frozen=True, slots=True)
class WorkloadBatchResult:
    """Environment-neutral receipt for one ordered task batch."""

    task_results: tuple[WorkloadTaskResult, ...]

    @property
    def success_rate(self) -> float:
        return sum(result.success for result in self.task_results) / max(1, len(self.task_results))

    @property
    def utility_mean(self) -> float:
        return sum(result.utility for result in self.task_results) / max(1, len(self.task_results))

    @property
    def total_steps(self) -> int:
        return sum(result.steps for result in self.task_results)

    @property
    def total_duration_s(self) -> float:
        return sum(result.duration_s for result in self.task_results)

    @property
    def memory_queries(self) -> int:
        return sum(result.memory_queries for result in self.task_results)

    @property
    def blocked_count(self) -> int:
        return sum(result.blocked for result in self.task_results)

    @property
    def failed_count(self) -> int:
        return sum(not result.success and not result.blocked for result in self.task_results)


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


__all__ = [
    "WorkloadBatchResult",
    "WorkloadCompletionReceipt",
    "WorkloadDecision",
    "WorkloadTaskResult",
    "WorkloadTaskRunError",
]
