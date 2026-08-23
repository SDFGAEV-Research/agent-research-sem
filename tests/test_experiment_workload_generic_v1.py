from __future__ import annotations

from research_platform.environment.runtime.api import ActionRequest, ActionResult, Observation
from research_platform.experimentation.experiment.api import ExperimentTaskSpec, FailureScope
from research_platform.experimentation.workload import (
    GenericWorkloadTaskRunner,
    WorkloadDecision,
)
from research_platform.participant.method.api import (
    MethodTaskCompletionReceipt,
    MethodTaskOutcome,
    RecallResult,
)
from research_platform.platform.kernel import ExecutionContext


class _Method:
    def __init__(self):
        self.outcomes = []

    def recall(self, request):
        return RecallResult("", "method-g0")

    def task_completed(self, result, context):
        self.outcomes.append(result)
        return MethodTaskCompletionReceipt(context.task_id or "task", "method-g0")


class _Environment:
    def __init__(self):
        self.requests: list[ActionRequest] = []

    def begin_task(self, metadata, context):
        return None

    def observe(self, context):
        return Observation("obs-0", "env-g0", {"state": {"done": False}})

    def act(self, request):
        self.requests.append(request)
        return ActionResult(
            request.action_id,
            True,
            Observation("obs-1", "env-g0", {"state": {"done": True}}),
            None,
            {"verified": True},
        )

    def end_task(self, metadata, context):
        return None


class _Evidence:
    def __init__(self):
        self.observations = []

    def ingest_observation(self, observation, context):
        self.observations.append(observation.observation_id)
        return (observation.observation_id,)


class _Planner:
    def decide(self, *, task, context, state, memory_context, step, prior_actions):
        return WorkloadDecision("advance", {"step": step}, "test")


class _State:
    def state(self, observation):
        return observation.payload["state"]


class _Completion:
    def is_complete(self, *, task, state, planner_finished, last_action):
        return bool(state.get("done"))

    def utility(self, *, task, success, state):
        return 1.0 if success else 0.0


class _FailurePolicy:
    def scope(self, phase, exception):
        del phase, exception
        return FailureScope.TASK


def test_generic_workload_runner_is_domain_neutral_and_preserves_action_identity():
    environment = _Environment()
    evidence = _Evidence()
    method = _Method()
    runner = GenericWorkloadTaskRunner(
        environment=environment,
        method=method,
        evidence=evidence,
        planner=_Planner(),
        state=_State(),
        completion=_Completion(),
        failure_policy=_FailurePolicy(),
    )

    result = runner.run(
        ExperimentTaskSpec("task-1", "navigation", "reach target", max_steps=2),
        ExecutionContext(run_id="run", trace_id="trace", span_id="span", study_id="study"),
    )

    assert result.success is True
    assert result.steps == 1
    assert environment.requests[0].action_id == "task-1:action:0"
    assert evidence.observations == ["obs-0", "obs-1"]
    assert method.outcomes == [
        MethodTaskOutcome(
            task_id="task-1",
            family="navigation",
            lineage_id="task-1",
            success=True,
            utility=1.0,
            steps=1,
            memory_queries=1,
        )
    ]
