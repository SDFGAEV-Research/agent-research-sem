from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from research_platform.environment.minecraft.api import (
    MinecraftBranchRuntimeFactoryPort,
    MinecraftBranchRuntimePort,
    MinecraftBranchRuntimeRequest,
    MinecraftWorldBranch,
)
from research_platform.participant.method.api import MethodObservationSink, MethodServices, MethodSession
from research_platform.platform.kernel import ExecutionContext, canonical_digest

from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole, CandidateArchitecture

from .minecraft_evidence import SEMMinecraftEvidenceIngestor, MinecraftEvidenceAdapter
from projects.sem_paper.method.self_evolving_memory.evidence_audit import AuditEvidenceStore
from .minecraft_runtime_adapter import MinecraftWorkloadEnvironmentAdapter
from .minecraft_workload import (
    MinecraftEvidencePort,
    MinecraftPlannerPort,
    MinecraftTaskSpec,
    MinecraftWorkloadDiagnosticsPort,
    MinecraftWorkloadEnvironmentPort,
)
from .project import SemPaperProjectComposition


class SemPaperWorkloadBindingError(RuntimeError):
    """A Paper workload binding failed before or during resource cleanup."""

    def __init__(
        self,
        message: str,
        *,
        phase: str,
        cause: BaseException | None = None,
        cleanup_errors: tuple[BaseException, ...] = (),
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.cause = cause
        self.cleanup_errors = cleanup_errors


class SemPaperBranchRuntimeRequestFactoryPort(Protocol):
    def build(
        self,
        *,
        role: BranchRole,
        candidate: CandidateArchitecture | None,
        branch: MinecraftWorldBranch,
    ) -> MinecraftBranchRuntimeRequest: ...


class SemPaperPlannerFactoryPort(Protocol):
    def create(
        self,
        *,
        role: BranchRole,
        candidate: CandidateArchitecture | None,
        task: MinecraftTaskSpec,
        method: MethodSession,
    ) -> MinecraftPlannerPort: ...


class SemPaperMethodObservationSinkFactoryPort(Protocol):
    def create(
        self,
        *,
        role: BranchRole,
        branch: MinecraftWorldBranch,
    ) -> MethodObservationSink: ...


class SemPaperMinecraftWorkloadBinding:
    """One fully opened Paper workload binding over a branch runtime."""

    def __init__(
        self,
        *,
        workload_id: str,
        task_manifest_digest: str,
        context: ExecutionContext,
        tasks: tuple[MinecraftTaskSpec, ...],
        environment: MinecraftWorkloadEnvironmentPort,
        method: MethodSession,
        evidence: MinecraftEvidencePort,
        diagnostics: MinecraftWorkloadDiagnosticsPort | None,
        runtime: MinecraftBranchRuntimePort,
    ) -> None:
        self.workload_id = workload_id
        self.environment_generation = runtime.environment_generation
        if not self.environment_generation.strip():
            raise ValueError("Paper workload binding requires environment generation evidence")
        self.task_manifest_digest = task_manifest_digest
        self.context = context
        self.tasks = tasks
        self.environment = environment
        self.method = method
        self.evidence = evidence
        self.diagnostics = diagnostics
        self.branch_writes: tuple[str, ...] = ()
        self.lifetime_writes: tuple[str, ...] = ()
        self.private_to_method_flows: tuple[str, ...] = ()
        self._runtime = runtime
        self._closed = False

    def planner_for(self, task: MinecraftTaskSpec) -> MinecraftPlannerPort:
        raise RuntimeError("planner binding was not attached")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        errors: list[BaseException] = []
        try:
            self.method.close()
        except BaseException as exc:
            errors.append(exc)
        try:
            self._runtime.close()
        except BaseException as exc:
            errors.append(exc)
        if errors:
            raise SemPaperWorkloadBindingError(
                f"Paper workload close failed ({len(errors)} cleanup errors)",
                phase="close",
                cleanup_errors=tuple(errors),
            ) from errors[0]


class _BoundSemPaperMinecraftWorkload(SemPaperMinecraftWorkloadBinding):
    def __init__(self, *, planner_factory: SemPaperPlannerFactoryPort, role: BranchRole, candidate: CandidateArchitecture | None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._planner_factory = planner_factory
        self._role = role
        self._candidate = candidate

    def planner_for(self, task: MinecraftTaskSpec) -> MinecraftPlannerPort:
        return self._planner_factory.create(
            role=self._role,
            candidate=self._candidate,
            task=task,
            method=self.method,
        )


class SemPaperMinecraftWorkloadBindingFactory:
    """Project-owned workload binder over the environment branch port."""

    def __init__(
        self,
        *,
        composition: SemPaperProjectComposition,
        branch_runtime_factory: MinecraftBranchRuntimeFactoryPort,
        request_factory: SemPaperBranchRuntimeRequestFactoryPort,
        planner_factory: SemPaperPlannerFactoryPort,
        observation_sink_factory: SemPaperMethodObservationSinkFactoryPort,
        tasks: tuple[MinecraftTaskSpec, ...],
        context: ExecutionContext,
        workload_id_factory: Callable[[BranchRole, MinecraftWorldBranch], str],
        diagnostics: MinecraftWorkloadDiagnosticsPort | None = None,
    ) -> None:
        if not tasks:
            raise ValueError("Paper workload binding requires an explicit non-empty task manifest")
        if not callable(workload_id_factory):
            raise ValueError("Paper workload_id_factory is required")
        self._composition = composition
        self._branch_runtime_factory = branch_runtime_factory
        self._request_factory = request_factory
        self._planner_factory = planner_factory
        self._observation_sink_factory = observation_sink_factory
        self._tasks = tasks
        self._context = context
        self._task_manifest_digest = canonical_digest(tasks)
        self._workload_id_factory = workload_id_factory
        self._diagnostics = diagnostics

    def open(
        self,
        *,
        role: BranchRole,
        candidate: CandidateArchitecture | None,
        branch: MinecraftWorldBranch,
    ) -> SemPaperMinecraftWorkloadBinding:
        if role is BranchRole.CONTROL and candidate is not None:
            raise SemPaperWorkloadBindingError("control workload received a candidate", phase="validate")
        if role is BranchRole.CANDIDATE:
            if candidate is None:
                raise SemPaperWorkloadBindingError("candidate workload has no candidate", phase="validate")
            if self._composition.bindings.candidate_method_materializer is None:
                raise SemPaperWorkloadBindingError(
                    "candidate method materializer is not composed",
                    phase="method_materialization",
                )
        request = self._request_factory.build(role=role, candidate=candidate, branch=branch)
        runtime = self._branch_runtime_factory.open(request)
        method: MethodSession | None = None
        try:
            endpoint = (
                self._composition.bindings.fixed_memory
                if role is BranchRole.CONTROL
                else self._composition.bindings.candidate_method_materializer.materialize(candidate)  # type: ignore[union-attr]
            )
            observation_sink = self._observation_sink_factory.create(role=role, branch=branch)
            services = MethodServices(observation_sink=observation_sink)
            environment_session = runtime.open_session(services)
            method = endpoint.open_session(
                session_id=f"{branch.branch_id}:method",
                services=services,
            )
            audit = AuditEvidenceStore()
            evidence = SEMMinecraftEvidenceIngestor(method, audit, MinecraftEvidenceAdapter())
            return _BoundSemPaperMinecraftWorkload(
                planner_factory=self._planner_factory,
                role=role,
                candidate=candidate,
                workload_id=self._workload_id_factory(role, branch),
                task_manifest_digest=self._task_manifest_digest,
                context=self._context,
                tasks=self._tasks,
                environment=MinecraftWorkloadEnvironmentAdapter(environment_session),
                method=method,
                evidence=evidence,
                diagnostics=self._diagnostics,
                runtime=runtime,
            )
        except BaseException as exc:
            errors: list[BaseException] = []
            if method is not None:
                try:
                    method.close()
                except BaseException as cleanup_exc:
                    errors.append(cleanup_exc)
            try:
                runtime.close()
            except BaseException as cleanup_exc:
                errors.append(cleanup_exc)
            if errors:
                raise SemPaperWorkloadBindingError(
                    "Paper workload open failed and cleanup failed",
                    phase="open",
                    cause=exc,
                    cleanup_errors=tuple(errors),
                ) from exc
            raise SemPaperWorkloadBindingError(
                "Paper workload open failed",
                phase="open",
                cause=exc,
            ) from exc


__all__ = [
    "SemPaperBranchRuntimeRequestFactoryPort",
    "SemPaperMethodObservationSinkFactoryPort",
    "SemPaperMinecraftWorkloadBinding",
    "SemPaperMinecraftWorkloadBindingFactory",
    "SemPaperPlannerFactoryPort",
    "SemPaperWorkloadBindingError",
]
