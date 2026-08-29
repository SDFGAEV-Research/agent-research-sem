from __future__ import annotations

from research_platform.participant.agent.api import (
    AgentActionSequence,
    AgentActionStep,
    AgentGoal,
    AgentMemoryContext,
    AgentModeDecision,
    AgentModeDisposition,
    AgentObservation,
    AgentSafetyDecision,
    AgentSafetyDisposition,
    AgentSkillDescription,
    AgentSkillSelection,
)
from research_platform.participant.agent.runtime.cognition_planning import (
    CognitionPlanningPhase,
    PlanningDisposition,
)
from research_platform.platform.kernel import ExecutionContext


class _Memory:
    def recall(self, goal, observation, context):
        del goal, context
        return AgentMemoryContext("memory", observation.generation)

    def record(self, receipt, context):
        del receipt, context


class _Planner:
    def plan(self, request):
        return AgentSkillSelection("skill.test", {"value": request.step})


class _Skills:
    def describe(self):
        return (AgentSkillDescription("skill.test", "test", "test skill", "{}", True),)

    def expand(self, selection, *, observation, context, sequence_id):
        del observation, context
        step = AgentActionStep(
            f"{sequence_id}:0", "move", dict(selection.arguments), selection.skill_id,
            sequence_id, 0,
        )
        return AgentActionSequence(sequence_id, selection.skill_id, (step,))


class _Completion:
    def is_complete(self, goal, observation, *, planner_finished, last_receipt):
        del goal, observation, planner_finished, last_receipt
        return False


class _Safety:
    def __init__(self, disposition, replacement=None):
        self.disposition = disposition
        self.replacement = replacement

    def review(self, goal, observation, selection, sequence, context):
        del goal, observation, selection, sequence, context
        return AgentSafetyDecision(self.disposition, "decision", "test", self.replacement)


class _Mode:
    def __init__(self, decision):
        self.decision = decision

    def review(self, goal, observation, selection, sequence, context):
        del goal, observation, selection, sequence, context
        return self.decision


def _replacement() -> AgentActionSequence:
    sequence_id = "replacement"
    step = AgentActionStep("replacement:0", "retreat", {}, "skill.test", sequence_id, 0)
    return AgentActionSequence(sequence_id, "skill.test", (step,))


def _phase(*, safety, mode=None):
    return CognitionPlanningPhase(
        memory=_Memory(), planner=_Planner(), skills=_Skills(), safety=safety,
        completion=_Completion(), skill_library=None, reactive_modes=mode,
        event=lambda *args, **kwargs: None, failure=lambda *args, **kwargs: None,
    )


def _plan(phase):
    return phase.plan(
        goal=AgentGoal("goal", "do task"),
        observation=AgentObservation("obs", "world", {"x": 1}),
        plan_context=ExecutionContext("run", "trace", "span"),
        step=0, plan_call=0, prior_actions=(), last_receipt=None,
    )


def test_safety_replan_is_a_typed_planning_outcome() -> None:
    result = _plan(_phase(safety=_Safety(AgentSafetyDisposition.REPLAN)))
    assert result.disposition is PlanningDisposition.REPLAN
    assert result.next_plan_call == 1


def test_reactive_mode_abort_is_distinct_from_safety_abort() -> None:
    mode = _Mode(AgentModeDecision("mode.stop", AgentModeDisposition.ABORT, "stop"))
    result = _plan(_phase(safety=_Safety(AgentSafetyDisposition.ALLOW), mode=mode))
    assert result.disposition is PlanningDisposition.MODE_ABORT


def test_preempted_sequence_crosses_phase_boundary_as_typed_sequence() -> None:
    replacement = _replacement()
    result = _plan(_phase(safety=_Safety(AgentSafetyDisposition.PREEMPT, replacement)))
    assert result.disposition is PlanningDisposition.EXECUTE
    assert result.sequence is replacement
    assert result.sequence.steps[0].action_type == "retreat"
