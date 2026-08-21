from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from research_platform.environment.minecraft.api import (
    MinecraftBranchRuntimeFactoryPort,
    MinecraftBranchServerFactoryPort,
    MinecraftServerConsolePort,
    MinecraftServerSpec,
    MinecraftWorldCutPort,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.resource.allocation.api import EndpointAllocationPort
from research_platform.scope.path.api import is_absolute_target_path

from ..providers.world_cut import (
    FilesystemMinecraftWorldCutProvider,
    MinecraftWorldCopier,
)
from ..providers.world_quiescence import MinecraftSaveQuiescenceProvider
from .branch_runtime import MinecraftBranchEnvironmentFactoryPort, MinecraftBranchRuntimeFactory


class MinecraftSourceServerPort(Protocol):
    """The source-server lifecycle facts required by a world-cut host."""

    contract: object

    def start(self) -> object: ...
    def reconcile(self) -> object: ...
    def stop(self) -> object: ...


@dataclass(frozen=True, slots=True)
class MinecraftExperimentHostInputs:
    """Generic MC host inputs shared by every project experiment.

    Project code supplies only its workload/request composition.  This value
    owns no paper method, task semantics, planner or candidate policy.
    """

    source_server_spec: MinecraftServerSpec
    source_console: MinecraftServerConsolePort
    source_server_factory: MinecraftBranchServerFactoryPort
    branch_server_factory: MinecraftBranchServerFactoryPort
    endpoint_allocations: EndpointAllocationPort
    environment_factory: MinecraftBranchEnvironmentFactoryPort
    snapshot_root: str | Path
    branch_root: str | Path
    source_environment_generation: str
    copier: MinecraftWorldCopier | None = None

    def __post_init__(self) -> None:
        if not self.source_environment_generation.strip():
            raise ValueError("Minecraft experiment source environment generation is required")
        for name, value in (("snapshot_root", self.snapshot_root), ("branch_root", self.branch_root)):
            if not is_absolute_target_path(Path(value).expanduser().resolve(strict=False)):
                raise ValueError(f"Minecraft experiment {name} must be an absolute path")
        if self.source_server_spec.rcon_endpoint is None:
            raise ValueError("Minecraft experiment source server requires an RCON endpoint for world cuts")


class MinecraftExperimentHost:
    """Reusable source-cut and branch-runtime host for MC experiments."""

    def __init__(
        self,
        *,
        source_server: MinecraftSourceServerPort,
        world_cuts: MinecraftWorldCutPort,
        branch_runtime_factory: MinecraftBranchRuntimeFactoryPort,
        source_process_holder: dict[str, object | None],
    ) -> None:
        self.source_server = source_server
        self.world_cuts = world_cuts
        self.branch_runtime_factory = branch_runtime_factory
        self._source_process_holder = source_process_holder
        self._started = False

    def start_source(self) -> object:
        if self._started:
            raise RuntimeError("Minecraft experiment source server is already started")
        outcome = self.source_server.start()
        process = getattr(outcome, "process", None)
        if process is None:
            raise RuntimeError("Minecraft source server start returned no process identity")
        self._source_process_holder["value"] = process
        self._started = True
        return outcome

    def process_identity_digest(self) -> str:
        observation = self.source_server.reconcile()
        process = getattr(observation, "process", None) or self._source_process_holder.get("value")
        if process is None:
            raise RuntimeError("Minecraft source server process identity is unavailable")
        return canonical_digest(process)

    def stop_source(self) -> object | None:
        if not self._started:
            return None
        try:
            return self.source_server.stop()
        finally:
            self._started = False
            self._source_process_holder["value"] = None

    def __enter__(self) -> "MinecraftExperimentHost":
        self.start_source()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop_source()
        return False


class LocalMinecraftExperimentHostFactory:
    """Compose local MC source/world-cut/branch authorities from injected ports."""

    def __init__(self, inputs: MinecraftExperimentHostInputs) -> None:
        self.inputs = inputs

    def open(self) -> MinecraftExperimentHost:
        inputs = self.inputs
        source_server = inputs.source_server_factory.create(
            inputs.source_server_spec,
            environment_generation=inputs.source_environment_generation,
        )
        source_process_holder: dict[str, object | None] = {"value": None}
        quiescence = MinecraftSaveQuiescenceProvider(
            console=inputs.source_console,
            source_workdir=inputs.source_server_spec.workdir,
            level_name=inputs.source_server_spec.level_name,
            server_contract_digest=source_server.contract.digest(),
            process_identity_digest=lambda: self._source_process_digest(source_server, source_process_holder),
        )
        world_cuts = FilesystemMinecraftWorldCutProvider(
            quiescence=quiescence,
            snapshot_root=inputs.snapshot_root,
            branch_root=inputs.branch_root,
            copier=inputs.copier,
        )
        branch_runtime_factory = MinecraftBranchRuntimeFactory(
            endpoint_allocations=inputs.endpoint_allocations,
            environment_factory=inputs.environment_factory,
            server_factory=inputs.branch_server_factory,
        )
        return MinecraftExperimentHost(
            source_server=source_server,
            world_cuts=world_cuts,
            branch_runtime_factory=branch_runtime_factory,
            source_process_holder=source_process_holder,
        )

    @staticmethod
    def _source_process_digest(
        source_server: MinecraftSourceServerPort,
        source_process_holder: dict[str, object | None],
    ) -> str:
        observation = source_server.reconcile()
        process = getattr(observation, "process", None) or source_process_holder.get("value")
        if process is None:
            raise RuntimeError("Minecraft source server process identity is unavailable")
        return canonical_digest(process)


__all__ = [
    "LocalMinecraftExperimentHostFactory",
    "MinecraftExperimentHost",
    "MinecraftExperimentHostInputs",
    "MinecraftSourceServerPort",
]
