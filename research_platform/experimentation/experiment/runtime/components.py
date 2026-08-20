from __future__ import annotations

from dataclasses import dataclass

from research_platform.experimentation.run.api import DecisionCycleCoordinatorPort, RunCoordinatorPort
from research_platform.experimentation.experiment.api import ExperimentWorkflowIdentity


@dataclass(frozen=True, slots=True)
class ExperimentRuntimeComponents:
    workflow_identity: ExperimentWorkflowIdentity
    cycle_coordinator: DecisionCycleCoordinatorPort
    run_coordinator: RunCoordinatorPort


__all__ = ["ExperimentRuntimeComponents"]
