from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from research_platform.environment.minecraft.api import MinecraftWorldCutPort
from research_platform.platform.kernel import ExecutionContext

from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole, PairedBranchEvaluator

from .minecraft_binding import (
    SemPaperBranchRuntimeRequestFactoryPort,
    SemPaperMethodObservationSinkFactoryPort,
    SemPaperMinecraftWorkloadBindingFactory,
    SemPaperPlannerFactoryPort,
)
from .minecraft_branch import MinecraftPairedBranchRunner
from .minecraft_workload import MinecraftTaskSpec, MinecraftWorkloadDiagnosticsPort
from .minecraft_workload_executor import MinecraftWorkloadBranchExecutor
from .project import SemPaperProjectComposition


@dataclass(frozen=True, slots=True)
class SemPaperMinecraftProductionRoot:
    """Frozen Paper production graph; no live resource is opened here."""

    composition: SemPaperProjectComposition
    workload_bindings: SemPaperMinecraftWorkloadBindingFactory
    workload_executor: MinecraftWorkloadBranchExecutor
    branch_runner: MinecraftPairedBranchRunner
    evaluator: PairedBranchEvaluator


def compose_sem_paper_minecraft_production_root(
    *,
    composition: SemPaperProjectComposition,
    world_cuts: MinecraftWorldCutPort,
    branch_runtime_factory,
    request_factory: SemPaperBranchRuntimeRequestFactoryPort,
    planner_factory: SemPaperPlannerFactoryPort,
    observation_sink_factory: SemPaperMethodObservationSinkFactoryPort,
    tasks: tuple[MinecraftTaskSpec, ...],
    context: ExecutionContext,
    workload_id_factory: Callable[[BranchRole, object], str],
    session_id: str,
    branch_id_factory: Callable[[BranchRole], str],
    destination_factory: Callable[[str], str],
    diagnostics: MinecraftWorkloadDiagnosticsPort | None = None,
) -> SemPaperMinecraftProductionRoot:
    """Freeze the sole project-to-Minecraft paired-evaluation composition graph."""

    bindings = SemPaperMinecraftWorkloadBindingFactory(
        composition=composition,
        branch_runtime_factory=branch_runtime_factory,
        request_factory=request_factory,
        planner_factory=planner_factory,
        observation_sink_factory=observation_sink_factory,
        tasks=tasks,
        context=context,
        workload_id_factory=workload_id_factory,
        diagnostics=diagnostics,
    )
    executor = MinecraftWorkloadBranchExecutor(bindings)
    runner = MinecraftPairedBranchRunner(
        world_cuts=world_cuts,
        executor=executor,
        session_id=session_id,
        context=context,
        branch_id_factory=branch_id_factory,
        destination_factory=destination_factory,
    )
    return SemPaperMinecraftProductionRoot(
        composition=composition,
        workload_bindings=bindings,
        workload_executor=executor,
        branch_runner=runner,
        evaluator=PairedBranchEvaluator(runner),
    )


__all__ = ["SemPaperMinecraftProductionRoot", "compose_sem_paper_minecraft_production_root"]
