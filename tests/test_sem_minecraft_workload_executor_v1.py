from __future__ import annotations

from dataclasses import dataclass

from projects.sem_paper.composition.minecraft_workload_executor import MinecraftWorkloadBranchExecutor
from projects.sem_paper.composition.minecraft_workload import (
    MinecraftEnvironmentActionResult,
    MinecraftEnvironmentObservation,
    MinecraftSuccessSpec,
    MinecraftTaskSpec,
    ScriptedMinecraftPlanner,
)
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from research_platform.environment.minecraft.api import MinecraftWorldBranch
from research_platform.participant.method.api import RecallResult
from research_platform.platform.kernel import ExecutionContext


class _Environment:
    def __init__(self) -> None:
        self.calls = 0

    def observe(self, context):
        self.calls += 1
        return MinecraftEnvironmentObservation(f"obs-{self.calls}", {"health": 20}, {"state": {"health": 20}})

    def begin_task(self, metadata, context):
        return None

    def end_task(self, metadata, context):
        return None

    def act(self, action_id, action_type, payload, context):
        return MinecraftEnvironmentActionResult(True, True, MinecraftEnvironmentObservation("obs-act", {"health": 20}, {}))


class _Method:
    def recall(self, request):
        return RecallResult("grounded memory", "generation-1")

    def ingest(self, evidence, context):
        return None

    def task_completed(self, result, context):
        return None


class _Evidence:
    def ingest_observation(self, observation, context):
        return ()


@dataclass
class _Binding:
    tasks: tuple[MinecraftTaskSpec, ...]
    environment: _Environment
    method: _Method
    evidence: _Evidence
    closed: bool = False
    workload_id: str = "workload-1"
    environment_generation: str = "environment-1"
    task_manifest_digest: str = "tasks-1"
    context: ExecutionContext = ExecutionContext("run-1", "trace-1", "span-1", task_id="")
    diagnostics: object = None
    branch_writes: tuple[str, ...] = ()
    lifetime_writes: tuple[str, ...] = ()
    private_to_method_flows: tuple[str, ...] = ()

    def planner_for(self, task):
        return ScriptedMinecraftPlanner(({"tool": "finish", "args": {}},))

    def record_result(self, *, task, result, context):
        return None

    def close(self):
        self.closed = True


class _Factory:
    def __init__(self, binding):
        self.binding = binding
        self.calls = []

    def open(self, *, role, candidate, branch):
        self.calls.append((role, candidate, branch.branch_id))
        return self.binding


def _branch() -> MinecraftWorldBranch:
    return MinecraftWorldBranch("branch-control", "cut-1", "C:/branches/control", "world", "a" * 64, "cleanup")


def test_workload_executor_runs_task_manifest_and_emits_aggregated_metrics() -> None:
    task = MinecraftTaskSpec(
        "task-1",
        "collect",
        "collect wood",
        max_steps=2,
        success=MinecraftSuccessSpec("health_positive"),
    )
    binding = _Binding((task,), _Environment(), _Method(), _Evidence())
    factory = _Factory(binding)
    result = MinecraftWorkloadBranchExecutor(factory).execute(role=BranchRole.CONTROL, candidate=None, branch=_branch())

    metrics = dict(result.metrics)
    assert metrics["task_count"] == 1.0
    assert metrics["success_rate"] == 1.0
    assert metrics["utility_mean"] == 1.0
    assert binding.closed is True
    assert factory.calls[0][0] is BranchRole.CONTROL
