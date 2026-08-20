from __future__ import annotations

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.core.api import BoundParticipants, ParticipantSessionBinding
from research_platform.execution.workflow.api import (
    EffectIntentOperationPort,
    OperationDispatchPort,
    ScientificCycleExecution,
    WorkflowSurfaceBindingContext,
    WorkflowSurfaceFactory,
    workflow_surface_id,
)
from research_platform.experimentation.experiment.api import ExperimentScientificWorkflow

from .workflow_surfaces import ExperimentWorkflowSurfaceRegistry


class ExperimentScientificCycleExecutor:
    """Binds generic operation ports to an injected workflow policy."""

    def __init__(
        self,
        dispatcher: OperationDispatchPort,
        workflow: ExperimentScientificWorkflow,
        *,
        effect_intents: EffectIntentOperationPort | None = None,
        workflow_surface_factories: tuple[WorkflowSurfaceFactory, ...] = (),
    ) -> None:
        self.dispatcher = dispatcher
        self.workflow = workflow
        self.effect_intents = effect_intents
        self._surface_registry = ExperimentWorkflowSurfaceRegistry(workflow_surface_factories)

    def execute(
        self,
        *,
        bound: BoundParticipants,
        participant_sessions: tuple[ParticipantSessionBinding, ...],
        context: ExecutionContext,
        task: object,
        input_kind: str,
        input_payload: object,
    ) -> ScientificCycleExecution:
        surface_context = WorkflowSurfaceBindingContext(
            self.dispatcher,
            bound,
            participant_sessions,
            self.effect_intents,
        )
        surface = self._surface_registry.bind(workflow_surface_id(self.workflow), surface_context)
        result = self.workflow.run(
            surface,
            context,
            task=task,
            input_kind=input_kind,
            input_payload=input_payload,
        )
        if not isinstance(result, ScientificCycleExecution):
            raise TypeError("ExperimentScientificWorkflow must return ScientificCycleExecution")
        return result


__all__ = ["ExperimentScientificCycleExecutor"]
