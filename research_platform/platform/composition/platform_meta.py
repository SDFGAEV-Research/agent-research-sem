from __future__ import annotations

from dataclasses import dataclass

from research_platform.artifact.catalog.api import ArtifactRegistryPort
from research_platform.artifact.catalog.runtime import InMemoryArtifactRegistry
from research_platform.data.dataset.api import DatasetRegistryPort
from research_platform.data.dataset.runtime import InMemoryDatasetRegistry
from research_platform.experimentation.catalog.api import ExperimentationCatalogPort
from research_platform.experimentation.catalog.runtime import InMemoryExperimentationCatalog
from research_platform.governance.system_registry.api import SystemRegistryPort
from research_platform.governance.system_registry.runtime import build_default_system_registry
from research_platform.portfolio.api import PortfolioCatalogPort
from research_platform.portfolio.runtime import InMemoryPortfolioCatalog
from research_platform.resource.compute.api import ComputeInventoryPort, ComputeSchedulerPort
from research_platform.resource.compute.runtime import InMemoryComputeInventory, InMemoryComputeScheduler
from research_platform.resource.core.api import ResourceLeasePort, ResourceOwnershipPort
from research_platform.resource.core.runtime import InMemoryResourceRegistry
from research_platform.environment.catalog.api import ExecutionEnvironmentCatalogPort
from research_platform.environment.catalog.runtime import ExecutionEnvironmentCatalog
from research_platform.scope.api import ScopeRegistryPort
from research_platform.scope.runtime import InMemoryScopeRegistry
from research_platform.governance.architecture.composition.capability_graph import (
    CapabilityCompositionPlanner,
)


@dataclass(frozen=True, slots=True)
class PlatformMetaAuthorities:
    """Behavior-free bundle used only by composition roots and top-level management surfaces."""

    systems: SystemRegistryPort
    scopes: ScopeRegistryPort
    capability_composition: CapabilityCompositionPlanner
    portfolio: PortfolioCatalogPort
    experimentation: ExperimentationCatalogPort
    environments: ExecutionEnvironmentCatalogPort
    artifacts: ArtifactRegistryPort
    datasets: DatasetRegistryPort
    resource_ownership: ResourceOwnershipPort
    resource_leases: ResourceLeasePort
    compute_inventory: ComputeInventoryPort
    compute_scheduler: ComputeSchedulerPort


def build_in_memory_platform_meta() -> PlatformMetaAuthorities:
    scopes = InMemoryScopeRegistry()
    systems = build_default_system_registry()
    resources = InMemoryResourceRegistry()
    compute_inventory = InMemoryComputeInventory()
    return PlatformMetaAuthorities(
        systems=systems,
        scopes=scopes,
        capability_composition=CapabilityCompositionPlanner(systems=systems, scopes=scopes),
        portfolio=InMemoryPortfolioCatalog(scopes),
        experimentation=InMemoryExperimentationCatalog(scopes),
        environments=ExecutionEnvironmentCatalog(scopes),
        artifacts=InMemoryArtifactRegistry(),
        datasets=InMemoryDatasetRegistry(),
        resource_ownership=resources,
        resource_leases=resources,
        compute_inventory=compute_inventory,
        compute_scheduler=InMemoryComputeScheduler(compute_inventory),
    )


__all__ = ["PlatformMetaAuthorities", "build_in_memory_platform_meta"]
