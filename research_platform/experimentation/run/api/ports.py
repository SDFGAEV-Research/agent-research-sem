from __future__ import annotations

from typing import Protocol, TypeVar

from research_platform.execution.decision.cycle_identity import DecisionCycleIdentity
from research_platform.execution.decision.cycle_result import DecisionCycleResult
from research_platform.experimentation.experiment.api import ExperimentSpec
from research_platform.experimentation.run.identity.api import RunIdentity
from research_platform.experimentation.run.lifecycle.api import RunSessionPort
from research_platform.platform.kernel import JsonInput


TaskT = TypeVar("TaskT")


class RunCoordinatorPort(Protocol):
    """Parent-facing lifecycle port for opening a long-lived run."""

    def open(
        self,
        spec: ExperimentSpec,
        identity: RunIdentity,
        *,
        restore_checkpoint_id: str | None = None,
        restore_cycle_identity: DecisionCycleIdentity | None = None,
    ) -> RunSessionPort: ...


class DecisionCycleCoordinatorPort(Protocol):
    """Parent-facing one-cycle execution port."""

    def run(
        self,
        spec: ExperimentSpec,
        identity: DecisionCycleIdentity,
        *,
        task: TaskT,
        input_kind: str,
        input_payload: JsonInput,
    ) -> DecisionCycleResult: ...


__all__ = ["DecisionCycleCoordinatorPort", "RunCoordinatorPort", "RunSessionPort"]
