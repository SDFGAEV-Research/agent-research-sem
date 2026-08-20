from __future__ import annotations

from typing import Protocol

from research_platform.execution.workflow.api import ScientificCycleExecution
from research_platform.participant.core.api import (
    BoundParticipants,
    ParticipantSessionBinding,
)
from research_platform.platform.kernel import ExecutionContext

from .contracts import ExperimentSpec


class ExperimentComponentBindingPort(Protocol):
    def bind(self, spec: ExperimentSpec, context: ExecutionContext) -> BoundParticipants: ...


class ExperimentScientificCycleExecutorPort(Protocol):
    def execute(
        self,
        *,
        bound: BoundParticipants,
        participant_sessions: tuple[ParticipantSessionBinding, ...],
        context: ExecutionContext,
        task: object,
        input_kind: str,
        input_payload: object,
    ) -> ScientificCycleExecution: ...


__all__ = ["ExperimentComponentBindingPort", "ExperimentScientificCycleExecutorPort"]
