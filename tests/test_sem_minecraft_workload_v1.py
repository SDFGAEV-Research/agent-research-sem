from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from projects.sem_paper.composition.minecraft_workload import (
    MinecraftEnvironmentActionResult,
    MinecraftEnvironmentObservation,
    MinecraftSuccessSpec,
    MinecraftTaskSpec,
    MinecraftWorkloadRunner,
    ScriptedMinecraftPlanner,
    evaluate_cognition_success,
    evaluate_success,
    task_from_mapping,
)
from research_platform.participant.agent.api import AgentObservation, AgentStepReceipt
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




def _action_receipt(action_id: str, action_type: str, action: dict, outcome: dict, *, verified: bool = True, state: dict | None = None) -> AgentStepReceipt:
    event = {
        "kind": "action_result",
        "sequence": 1,
        "timestamp_ms": 1,
        "payload": {
            "action_id": action_id,
            "action": {"tool": action_type, **action},
            "outcome": outcome,
            "verified": verified,
        },
    }
    observation = AgentObservation(
        f"obs:{action_id}",
        "minecraft-test",
        state or {"anchors": {"spawn": {"x": 10.5, "y": 65.0, "z": -4.5}}},
        evidence_payload={"events": [event]},
    )
    return AgentStepReceipt(
        action_id, action_type, f"minecraft.{action_type}", f"seq:{action_id}",
        True, verified, observation=observation, effect_certainty="confirmed",
    )


def test_blueprint_success_requires_complete_grounded_placement_receipts() -> None:
    spec = MinecraftSuccessSpec(
        "blueprint_complete",
        {
            "anchor": "spawn",
            "blocks": [
                {"offset": {"x": 2, "y": 0, "z": 0}, "block": "crafting_table"},
                {"offset": {"x": 3, "y": 0, "z": 0}, "block": "chest"},
            ],
        },
    )
    task = MinecraftTaskSpec(
        "build", "simple_building", "build station",
        referenced_anchors=("spawn",), success=spec,
    )
    table = _action_receipt(
        "a1", "place_block",
        {"item": "crafting_table", "position": {"x": 12, "y": 65, "z": -5}},
        {"status": "applied", "code": "BLOCK_PLACED", "position": {"x": 12, "y": 65, "z": -5}, "placed": "crafting_table"},
    )
    chest = _action_receipt(
        "a2", "place_block",
        {"item": "chest", "position": {"x": 13, "y": 65, "z": -5}},
        {"status": "applied", "code": "BLOCK_PLACED", "position": {"x": 13, "y": 65, "z": -5}, "placed": "chest"},
    )
    final = AgentObservation(
        "obs:final", "minecraft-test",
        {"anchors": {"spawn": {"x": 10.5, "y": 65.0, "z": -4.5}}},
    )
    result = SimpleNamespace(success=True, action_receipts=(table, chest), final_observation=final)
    assert evaluate_cognition_success(task, result) is True
    missing = SimpleNamespace(success=True, action_receipts=(table,), final_observation=final)
    assert evaluate_cognition_success(task, missing) is False


def test_blueprint_success_is_revoked_when_target_block_is_later_removed() -> None:
    spec = MinecraftSuccessSpec(
        "blueprint_complete",
        {
            "anchor": "spawn",
            "blocks": [
                {"offset": {"x": 2, "y": 0, "z": 0}, "block": "crafting_table"},
                {"offset": {"x": 3, "y": 0, "z": 0}, "block": "chest"},
            ],
        },
    )
    task = MinecraftTaskSpec(
        "build", "simple_building", "build station",
        referenced_anchors=("spawn",), success=spec,
    )
    table = _action_receipt(
        "a1", "place_block", {"item": "crafting_table", "position": {"x": 12, "y": 65, "z": -5}},
        {"status": "applied", "code": "BLOCK_PLACED", "position": {"x": 12, "y": 65, "z": -5}, "placed": "crafting_table"},
    )
    chest = _action_receipt(
        "a2", "place_block", {"item": "chest", "position": {"x": 13, "y": 65, "z": -5}},
        {"status": "applied", "code": "BLOCK_PLACED", "position": {"x": 13, "y": 65, "z": -5}, "placed": "chest"},
    )
    removed = _action_receipt(
        "a3", "collect_block", {"block": "chest", "count": 1, "max_distance": 48},
        {"status": "applied", "code": "BLOCKS_COLLECTED", "broken": [{"name": "chest", "position": {"x": 13, "y": 65, "z": -5}}]},
    )
    final = AgentObservation(
        "obs:final-removed", "minecraft-test",
        {"anchors": {"spawn": {"x": 10.5, "y": 65.0, "z": -4.5}}},
    )
    result = SimpleNamespace(success=True, action_receipts=(table, chest, removed), final_observation=final)
    assert evaluate_cognition_success(task, result) is False


def test_navigation_success_requires_verified_departure_and_later_return() -> None:
    task = MinecraftTaskSpec(
        "nav", "navigation_return", "away and back", referenced_anchors=("spawn",),
        success=MinecraftSuccessSpec("away_then_return", {"anchor": "spawn", "min_departure_distance": 16, "return_radius": 5}),
    )
    anchor = {"x": 0.0, "y": 64.0, "z": 0.0}
    depart = _action_receipt(
        "n1", "goto", {"position": {"x": 20, "y": 64, "z": 0}, "radius": 1.5},
        {"status": "applied", "code": "TARGET_REACHED", "target": {"x": 20, "y": 64, "z": 0}, "position": {"x": 20, "y": 64, "z": 0}, "distance": 0.0, "within_radius": True},
        state={"anchors": {"spawn": anchor}, "position": {"x": 20.0, "y": 64.0, "z": 0.0}},
    )
    returned = _action_receipt(
        "n2", "goto", {"position": {"x": 0, "y": 64, "z": 0}, "radius": 1.5},
        {"status": "applied", "code": "TARGET_REACHED", "target": {"x": 0, "y": 64, "z": 0}, "position": {"x": 1, "y": 64, "z": 0}, "distance": 1.0, "within_radius": True},
        state={"anchors": {"spawn": anchor}, "position": {"x": 1.0, "y": 64.0, "z": 0.0}},
    )
    final = AgentObservation("nav-final", "minecraft-test", {"anchors": {"spawn": anchor}, "position": {"x": 1.0, "y": 64.0, "z": 0.0}})
    assert evaluate_cognition_success(task, SimpleNamespace(success=True, action_receipts=(depart, returned), final_observation=final)) is True
    assert evaluate_cognition_success(task, SimpleNamespace(success=True, action_receipts=(returned,), final_observation=final)) is False


def test_combat_success_requires_meaningful_verified_combat_and_survival() -> None:
    task = MinecraftTaskSpec(
        "combat", "combat_survival", "fight and survive",
        success=MinecraftSuccessSpec("combat_survived", {"min_verified_combat_actions": 1}),
    )
    hit = _action_receipt(
        "c1", "attack_nearest", {"entity": "zombie", "max_distance": 16, "max_hits": 4},
        {"status": "applied", "code": "TARGET_HIT_CONFIRMED", "target_id": 7, "hits": 1, "hurt_signals": 1, "target_valid_after": True},
        state={"health": 16.0},
    )
    final = AgentObservation("combat-final", "minecraft-test", {"health": 16.0})
    assert evaluate_cognition_success(task, SimpleNamespace(success=True, action_receipts=(hit,), final_observation=final)) is True
    no_threat = _action_receipt(
        "c2", "defend_self", {"radius": 12, "max_targets": 4, "max_hits": 12},
        {"status": "applied", "code": "NO_THREATS", "targets_observed": 0},
        state={"health": 20.0},
    )
    assert evaluate_cognition_success(task, SimpleNamespace(success=True, action_receipts=(no_threat,), final_observation=final)) is False
    dead = AgentObservation("combat-dead", "minecraft-test", {"health": 0.0})
    assert evaluate_cognition_success(task, SimpleNamespace(success=True, action_receipts=(hit,), final_observation=dead)) is False
