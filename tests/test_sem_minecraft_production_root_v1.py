from __future__ import annotations

from types import SimpleNamespace

from projects.sem_paper.composition import (
    SemPaperMinecraftProductionRoot,
    compose_sem_paper_minecraft_production_root,
)
from projects.sem_paper.composition.minecraft_workload import MinecraftTaskSpec
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from research_platform.platform.kernel import ExecutionContext


def test_production_root_freezes_the_unique_paired_graph_without_opening_resources() -> None:
    composition = SimpleNamespace(bindings=SimpleNamespace(fixed_memory=object(), candidate_method_materializer=None))
    root = compose_sem_paper_minecraft_production_root(
        composition=composition,
        world_cuts=object(),
        branch_runtime_factory=object(),
        request_factory=object(),
        planner_factory=object(),
        observation_sink_factory=object(),
        tasks=(MinecraftTaskSpec("task-1", "collection", "collect wood"),),
        context=ExecutionContext("run-1", "trace-1", "span-1"),
        workload_id_factory=lambda role, branch: f"{role.value}:workload",
        session_id="paper-session",
        branch_id_factory=lambda role: f"{role.value}-branch",
        destination_factory=lambda branch_id: f"C:/mc/{branch_id}",
    )

    assert isinstance(root, SemPaperMinecraftProductionRoot)
    assert root.composition is composition
    assert root.evaluator.runner is root.branch_runner
    assert root.workload_executor.bindings is root.workload_bindings
    assert root.branch_runner.executor is root.workload_executor
