from __future__ import annotations

from dataclasses import dataclass

from projects.sem_paper.composition.minecraft_workload import (
    MinecraftEnvironmentActionResult,
    MinecraftEnvironmentObservation,
    MinecraftSuccessSpec,
    MinecraftTaskSpec,
    MinecraftWorkloadRunner,
    ScriptedMinecraftPlanner,
    evaluate_success,
    task_from_mapping,
)
from research_platform.participant.method.api import MethodTaskCompletionReceipt, RecallResult
from research_platform.platform.kernel import ExecutionContext


class _Method:
    def __init__(self) -> None:
        self.recall_requests = []
        self.completed = []

    def recall(self, request):
        self.recall_requests.append(request)
        return RecallResult("prior grounded memory", "generation-1")

    def ingest(self, evidence, context):
        del evidence, context

    def task_completed(self, result, context):
        self.completed.append((result, context))
        return MethodTaskCompletionReceipt(result["task_id"], "generation-1")


class _Evidence:
    def __init__(self) -> None:
        self.observations = []

    def ingest_observation(self, observation, context):
        self.observations.append((observation, context))
        return (f"evidence-{len(self.observations)}",)


class _FailingDiagnostics:
    def event(self, event, *, attributes=None, level="DEBUG"):
        del event, attributes, level
        raise RuntimeError("event sink unavailable")

    def metric(self, name, value, *, labels=None):
        del name, value, labels
        raise RuntimeError("metric sink unavailable")

    def failure(self, code, message, *, phase):
        del code, message, phase
        raise RuntimeError("failure sink unavailable")


@dataclass
class _Environment:
    actions: list[tuple[str, str, dict, ExecutionContext]]

    def observe(self, context):
        return MinecraftEnvironmentObservation(
            "observation-0",
            {"inventory": {}, "last_action_verified": None},
            {"events": []},
        )

    def act(self, action_id, action_type, payload, context):
        self.actions.append((action_id, action_type, dict(payload), context))
        return MinecraftEnvironmentActionResult(
            accepted=True,
            verified=True,
            observation=MinecraftEnvironmentObservation(
                "observation-1",
                {"inventory": {"oak_log": 1}, "last_action_verified": True},
                {"events": []},
            ),
            payload={"ok": True},
        )


def test_task_mapping_and_success_predicate_preserve_v034_task_semantics() -> None:
    task = task_from_mapping(
        {
            "task_id": "gather-1",
            "goal": "Gather one log",
            "family": "gather",
            "max_steps": 2,
            "success": {"kind": "inventory_min", "item": "re:.*_log$", "count": 1},
        }
    )
    assert task.task_id == "gather-1"
    assert evaluate_success(task, {"inventory": {"oak_log": 1}}, planner_finished=False) is True


def test_workload_runner_uses_injected_environment_method_evidence_and_planner_ports() -> None:
    method = _Method()
    evidence = _Evidence()
    environment = _Environment([])
    runner = MinecraftWorkloadRunner(
        environment=environment,
        method=method,
        evidence=evidence,
        planner=ScriptedMinecraftPlanner(
            (
                {"tool": "wait", "args": {"ms": 1}},
                {"tool": "finish", "args": {"reason": "inventory_ready"}},
            )
        ),
    )
    task = MinecraftTaskSpec(
        task_id="gather-1",
        family="gather",
        goal="Gather one log",
        max_steps=3,
        success=type(task_from_mapping({"task_id": "x", "goal": "x"}).success)(
            "inventory_min", {"item": "oak_log", "count": 1}
        ),
    )
    context = ExecutionContext("run-1", "trace-1", "span-1")

    result = runner.run(task, context)

    assert result.success is True
    assert result.steps == 1
    assert result.memory_queries == 1
    assert len(method.recall_requests) == 1
    assert len(method.completed) == 1
    assert method.completed[0][0]["success"] is True
    assert environment.actions[0][1] == "wait"
    assert len(evidence.observations) == 2
    assert environment.actions[0][3].decision_cycle_id == "gather-1:cycle:0"


def test_workload_runner_completes_failed_attempt_without_claiming_success() -> None:
    method = _Method()
    runner = MinecraftWorkloadRunner(
        environment=_Environment([]),
        method=method,
        evidence=_Evidence(),
        planner=ScriptedMinecraftPlanner(({"tool": "finish", "args": {"reason": "stop"}},)),
    )
    task = MinecraftTaskSpec(
        task_id="observe",
        family="exploration",
        goal="Observe",
        max_steps=1,
        success=MinecraftSuccessSpec("last_action_verified", {}),
    )

    result = runner.run(task, ExecutionContext("run-1", "trace-1", "span-1"))

    assert result.success is False
    assert result.failure_reason == "success_predicate_not_satisfied"
    assert method.completed[0][0]["success"] is False


def test_workload_runner_retains_diagnostic_sink_errors_without_masking_task_result() -> None:
    method = _Method()
    runner = MinecraftWorkloadRunner(
        environment=_Environment([]),
        method=method,
        evidence=_Evidence(),
        planner=ScriptedMinecraftPlanner(({"tool": "finish", "args": {}},)),
        diagnostics=_FailingDiagnostics(),
    )
    task = MinecraftTaskSpec(
        task_id="diagnostic-tail",
        family="smoke",
        goal="Observe",
        success=MinecraftSuccessSpec("always"),
    )

    result = runner.run(task, ExecutionContext("run-1", "trace-1", "span-1"))

    assert result.success is True
    errors = result.diagnostics["diagnostic_sink_errors"]
    assert len(errors) >= 2
    assert any(str(error).startswith("event:") for error in errors)

def test_planner_finish_requires_positive_environment_verification() -> None:
    task = MinecraftTaskSpec(
        task_id="finish-only",
        family="scientific",
        goal="Do not self-certify",
        max_steps=1,
        success=MinecraftSuccessSpec("planner_finish", {}),
    )

    assert evaluate_success(task, {}, planner_finished=True) is False
    assert evaluate_success(
        task, {"last_action_verified": None}, planner_finished=True
    ) is False
    assert evaluate_success(
        task, {"last_action_verified": False}, planner_finished=True
    ) is False
    assert evaluate_success(
        task, {"last_action_verified": True}, planner_finished=True
    ) is True

    runner = MinecraftWorkloadRunner(
        environment=_Environment([]),
        method=_Method(),
        evidence=_Evidence(),
        planner=ScriptedMinecraftPlanner(({"tool": "finish", "args": {}},)),
    )
    result = runner.run(
        task, ExecutionContext("run-1", "trace-1", "span-1")
    )
    assert result.success is False
    assert result.failure_reason == "success_predicate_not_satisfied"
