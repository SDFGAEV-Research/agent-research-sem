from __future__ import annotations

from research_platform.participant.agent.api import (
    AgentEvidencePort,
    AgentPlannerPort,
    AgentPlanningRequest,
    AgentProgressPort,
    AgentSkillSelection,
)
from research_platform.platform.kernel import ExecutionContext

from .minecraft_workload import (
    MinecraftEnvironmentObservation,
    MinecraftEvidencePort,
    MinecraftPlannerPort,
    MinecraftTaskSpec,
)


class SemPaperCognitionPlannerAdapter(AgentPlannerPort):
    """Adapt the existing Paper planner ABI to the generic cognition ABI."""

    def __init__(self, planner: MinecraftPlannerPort, task: MinecraftTaskSpec) -> None:
        self._planner = planner
        self._task = task

    def plan(self, request: AgentPlanningRequest) -> AgentSkillSelection:
        prior_actions = tuple(
            {
                "action_id": summary.action_id,
                "action_type": summary.action_type,
                "accepted": summary.accepted,
                "verified": summary.verified,
                "payload": dict(summary.payload),
            }
            for summary in request.prior_actions
        )
        decision = self._planner.decide(
            task=self._task,
            context=request.context,
            state=request.observation.state,
            memory_context=request.memory.context_text,
            step=request.step,
            prior_actions=prior_actions,
        )
        if decision.action_type == "finish":
            return AgentSkillSelection("minecraft.finish", dict(decision.payload), completion_claim=True, rationale=decision.rationale)
        return AgentSkillSelection(f"minecraft.{decision.action_type}", dict(decision.payload), rationale=decision.rationale)


class SemPaperCognitionEvidenceAdapter(AgentEvidencePort):
    def __init__(self, evidence: MinecraftEvidencePort) -> None:
        self._evidence = evidence

    def ingest(self, observation, context: ExecutionContext) -> None:
        self._evidence.ingest_observation(
            MinecraftEnvironmentObservation(
                observation.observation_id,
                dict(observation.state),
                {"state": dict(observation.state), "modality": observation.modality},
            ),
            context,
        )


class SemPaperCognitionProgressAdapter(AgentProgressPort):
    """Explicit checkpoint seam; persistence remains owned by composition."""

    def __init__(self, persist) -> None:
        if not callable(persist):
            raise ValueError("cognition checkpoint persist callback is required")
        self._persist = persist

    def persist(self, checkpoint, context: ExecutionContext) -> None:
        self._persist(checkpoint, context)


__all__ = [
    "SemPaperCognitionEvidenceAdapter",
    "SemPaperCognitionPlannerAdapter",
    "SemPaperCognitionProgressAdapter",
]
