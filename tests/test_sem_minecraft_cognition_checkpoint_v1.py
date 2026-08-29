from __future__ import annotations

import json

import pytest

from projects.sem_paper.composition.minecraft_cognition_checkpoint import (
    MinecraftCognitionCheckpointState,
)
from projects.sem_paper.composition.minecraft_workload import (
    MinecraftSuccessSpec,
    MinecraftTaskSpec,
    MinecraftWorkloadRunner,
)
from research_platform.participant.agent.api import (
    AgentActionSummary,
    AgentLoopCheckpoint,
    AgentLoopResult,
    AgentLoopTerminationReason,
    AgentObservation,
)
from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodTaskCompletionReceipt


def _checkpoint_schema_version() -> str:
    return (
        "agent-cognition-checkpoint.v2"
        if "last_receipt" in getattr(AgentLoopCheckpoint, "__dataclass_fields__", {})
        else "agent-cognition-checkpoint.v1"
    )


def _checkpoint(*, step: int = 1, plan_calls: int = 1) -> AgentLoopCheckpoint:
    summary = AgentActionSummary(
        action_id="action-1", action_type="wait", skill_id="minecraft.wait",
        accepted=True, verified=True, observation_digest="c" * 64, payload={"ms": 1},
    )
    kwargs = {}
    if "last_receipt" in getattr(AgentLoopCheckpoint, "__dataclass_fields__", {}):
        from research_platform.participant.agent.api import AgentReceiptCheckpoint
        kwargs["last_receipt"] = AgentReceiptCheckpoint(
            "action-1", "wait", "minecraft.wait", "sequence-1", True, True
        )
    return AgentLoopCheckpoint(
        schema_version=_checkpoint_schema_version(),
        session_id="run-1:branch-1:task-1", goal_digest="a" * 64,
        step=step, plan_calls=plan_calls, no_progress_steps=0, same_action_runs=1,
        last_observation_digest="b" * 64, action_summaries=(summary,), **kwargs,
    )


def test_cognition_checkpoint_component_round_trips_exact_typed_state() -> None:
    state = MinecraftCognitionCheckpointState()
    checkpoint = _checkpoint()
    state.progress_for("task-1").persist(
        checkpoint,
        ExecutionContext("run-1", "trace-1", "span-1", task_id="task-1"),
    )

    payload = state.capture()
    restored = MinecraftCognitionCheckpointState()
    restored.restore(payload)

    value = restored.checkpoint_for("task-1")
    assert value == checkpoint
    assert value is not None and value.digest == checkpoint.digest


def test_cognition_checkpoint_restore_is_fail_closed_and_transactional() -> None:
    state = MinecraftCognitionCheckpointState()
    original = _checkpoint()
    state.progress_for("task-1").persist(
        original,
        ExecutionContext("run-1", "trace-1", "span-1", task_id="task-1"),
    )
    document = json.loads(state.capture().decode("utf-8"))
    document["checkpoints"][0]["checkpoint"]["unexpected"] = True

    with pytest.raises(ValueError, match="fields are not exact"):
        state.restore(json.dumps(document).encode("utf-8"))

    assert state.checkpoint_for("task-1") == original


def test_cognition_checkpoint_rejects_identity_drift_and_counter_regression() -> None:
    state = MinecraftCognitionCheckpointState()
    context = ExecutionContext("run-1", "trace-1", "span-1", task_id="task-1")
    state.persist_for("task-1", _checkpoint(step=2, plan_calls=2), context)

    with pytest.raises(ValueError, match="cannot regress"):
        state.persist_for("task-1", _checkpoint(step=1, plan_calls=2), context)
    with pytest.raises(ValueError, match="task identity"):
        state.persist_for(
            "task-1",
            _checkpoint(step=3, plan_calls=3),
            ExecutionContext("run-1", "trace-1", "span-1", task_id="other"),
        )


class _Method:
    def __init__(self) -> None:
        self.completions = []

    def recall(self, request):  # pragma: no cover - fake cognition runner owns execution
        raise AssertionError(request)

    def task_completed(self, result, context):
        self.completions.append((result, context))
        return MethodTaskCompletionReceipt(f"task:{context.run_id}:{context.task_id}", "g0")


class _Evidence:
    def ingest_observation(self, observation, context):  # pragma: no cover
        raise AssertionError((observation, context))


class _Environment:
    session = object()


class _Planner:
    pass


class _FakeCognitionRunner:
    def __init__(self, progress, calls) -> None:
        self._progress = progress
        self._calls = calls

    def run(self, goal, context, *, session_id, checkpoint=None):
        self._calls.append((goal, session_id, checkpoint))
        next_step = 1 if checkpoint is None else checkpoint.step + 1
        next_plan_calls = 1 if checkpoint is None else checkpoint.plan_calls + 1
        value = AgentLoopCheckpoint(
            schema_version=_checkpoint_schema_version(),
            session_id=session_id,
            goal_digest=goal.digest,
            step=next_step,
            plan_calls=next_plan_calls,
            no_progress_steps=0,
            same_action_runs=0,
            last_observation_digest="d" * 64,
        )
        self._progress.persist(value, context)
        observation = AgentObservation("obs-1", "generation-1", {})
        return AgentLoopResult(
            success=False,
            termination=AgentLoopTerminationReason.MAX_STEPS,
            steps=next_step,
            plan_calls=next_plan_calls,
            memory_queries=0,
            selected_skills=(),
            action_receipts=(),
            final_observation=observation,
            checkpoint=value,
            failure_code="AGENT_MAX_STEPS",
        )


class _FakeCognitionFactory:
    def __init__(self) -> None:
        self.calls = []

    def create(self, *, session, planner, evidence, progress, memory, diagnostics):
        del session, planner, evidence, memory, diagnostics
        return _FakeCognitionRunner(progress, self.calls)


def test_workload_cognition_uses_binding_owned_checkpoint_and_hardens_planner_finish() -> None:
    state = MinecraftCognitionCheckpointState()
    factory = _FakeCognitionFactory()
    task = MinecraftTaskSpec(
        task_id="task-1",
        family="scientific",
        goal="perform a grounded action",
        success=MinecraftSuccessSpec("planner_finish"),
    )
    context = ExecutionContext(
        "run-1", "trace-1", "span-1", branch_id="branch-1", task_id="task-1"
    )

    first_method = _Method()
    first = MinecraftWorkloadRunner(
        environment=_Environment(),
        method=first_method,
        evidence=_Evidence(),
        planner=_Planner(),
        cognition_factory=factory,
        cognition_checkpoints=state,
    )
    first_result = first.run(task, context)
    assert first_result.completion_receipt is not None
    assert first_result.completion_receipt.completion_key == "task:run-1:task-1"
    assert len(first_method.completions) == 1
    completion_outcome, completion_context = first_method.completions[0]
    assert completion_outcome.task_id == "task-1"
    assert completion_context.task_id == "task-1"
    assert completion_context.decision_cycle_id is None
    stored = state.checkpoint_for("task-1")
    assert stored is not None
    assert factory.calls[0][0].context["success"] == {"kind": "last_action_verified"}
    assert factory.calls[0][2] is None

    second = MinecraftWorkloadRunner(
        environment=_Environment(),
        method=_Method(),
        evidence=_Evidence(),
        planner=_Planner(),
        cognition_factory=factory,
        cognition_checkpoints=state,
    )
    second.run(task, context)
    assert factory.calls[1][2] == stored
    assert state.checkpoint_for("task-1").step == stored.step + 1
