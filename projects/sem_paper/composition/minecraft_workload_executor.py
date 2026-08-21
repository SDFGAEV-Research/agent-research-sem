from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from typing import Protocol

from research_platform.participant.method.api import MethodSession
from research_platform.platform.kernel import ExecutionContext

from projects.sem_paper.method.self_evolving_memory.evolution import (
    BranchRole,
    CandidateArchitecture,
)

from .minecraft_branch import (
    MinecraftBranchExecutionResult,
    MinecraftBranchExecutorPort,
)
from .minecraft_workload import (
    MinecraftEvidencePort,
    MinecraftPlannerPort,
    MinecraftTaskRunResult,
    MinecraftTaskSpec,
    MinecraftWorkloadDiagnosticsPort,
    MinecraftWorkloadEnvironmentPort,
    MinecraftWorkloadRunner,
)
from research_platform.environment.minecraft.api import MinecraftWorldBranch


class MinecraftWorkloadBindingCloseError(RuntimeError):
    """The injected branch workload binding could not close cleanly."""


class MinecraftWorkloadBindingPort(Protocol):
    workload_id: str
    environment_generation: str
    task_manifest_digest: str
    context: ExecutionContext
    tasks: tuple[MinecraftTaskSpec, ...]
    environment: MinecraftWorkloadEnvironmentPort
    method: MethodSession
    evidence: MinecraftEvidencePort
    diagnostics: MinecraftWorkloadDiagnosticsPort | None
    branch_writes: tuple[str, ...]
    lifetime_writes: tuple[str, ...]
    private_to_method_flows: tuple[str, ...]

    def planner_for(self, task: MinecraftTaskSpec) -> MinecraftPlannerPort: ...

    def close(self) -> None: ...


class MinecraftWorkloadBindingFactoryPort(Protocol):
    def open(
        self,
        *,
        role: BranchRole,
        candidate: CandidateArchitecture | None,
        branch: MinecraftWorldBranch,
    ) -> MinecraftWorkloadBindingPort: ...


@dataclass(frozen=True, slots=True)
class MinecraftWorkloadBatchResult:
    task_results: tuple[MinecraftTaskRunResult, ...]

    @property
    def success_rate(self) -> float:
        return sum(result.success for result in self.task_results) / max(1, len(self.task_results))

    @property
    def utility_mean(self) -> float:
        return sum(result.utility for result in self.task_results) / max(1, len(self.task_results))

    @property
    def total_steps(self) -> int:
        return sum(result.steps for result in self.task_results)

    @property
    def total_duration_s(self) -> float:
        return sum(result.duration_s for result in self.task_results)

    @property
    def memory_queries(self) -> int:
        return sum(result.memory_queries for result in self.task_results)


class MinecraftWorkloadBranchExecutor(MinecraftBranchExecutorPort):
    """Execute a branch's task manifest using only injected project bindings."""

    def __init__(self, bindings: MinecraftWorkloadBindingFactoryPort) -> None:
        self.bindings = bindings

    def execute(
        self,
        *,
        role: BranchRole,
        candidate: CandidateArchitecture | None,
        branch: MinecraftWorldBranch,
    ) -> MinecraftBranchExecutionResult:
        binding = self.bindings.open(role=role, candidate=candidate, branch=branch)
        primary_error: BaseException | None = None
        batch: MinecraftWorkloadBatchResult | None = None
        try:
            results: list[MinecraftTaskRunResult] = []
            for task in binding.tasks:
                result = MinecraftWorkloadRunner(
                    environment=binding.environment,
                    method=binding.method,
                    evidence=binding.evidence,
                    planner=binding.planner_for(task),
                    diagnostics=binding.diagnostics,
                ).run(task, binding.context)
                results.append(result)
            batch = MinecraftWorkloadBatchResult(tuple(results))
        except BaseException as exc:
            primary_error = exc

        try:
            binding.close()
        except BaseException as exc:
            if primary_error is not None:
                raise MinecraftWorkloadBindingCloseError(
                    "branch workload failed and binding close failed"
                ) from exc
            raise MinecraftWorkloadBindingCloseError("branch workload binding close failed") from exc

        if primary_error is not None:
            raise primary_error
        assert batch is not None
        metrics = (
            ("task_count", float(len(batch.task_results))),
            ("success_rate", batch.success_rate),
            ("utility_mean", batch.utility_mean),
            ("steps_total", float(batch.total_steps)),
            ("duration_s_total", batch.total_duration_s),
            ("memory_queries_total", float(batch.memory_queries)),
        )
        if any(not math.isfinite(value) for _, value in metrics):
            raise ValueError("Minecraft workload batch produced a non-finite metric")
        return MinecraftBranchExecutionResult(
            workload_id=binding.workload_id,
            environment_generation=binding.environment_generation,
            task_manifest_digest=binding.task_manifest_digest,
            metrics=metrics,
            branch_writes=binding.branch_writes,
            lifetime_writes=binding.lifetime_writes,
            private_to_method_flows=binding.private_to_method_flows,
        )


__all__ = [
    "MinecraftWorkloadBatchResult",
    "MinecraftWorkloadBindingCloseError",
    "MinecraftWorkloadBindingFactoryPort",
    "MinecraftWorkloadBindingPort",
    "MinecraftWorkloadBranchExecutor",
]
