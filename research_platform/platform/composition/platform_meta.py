from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
from research_platform.resource.allocation.api import EndpointAllocationPort
from research_platform.resource.allocation.providers import SocketEndpointProbe
from research_platform.resource.providers import (
    SQLiteEndpointAllocationStore,
    SQLiteResourceLeaseRegistry,
)
from research_platform.resource.allocation.runtime import AtomicEndpointAllocator, InMemoryEndpointAllocator
from research_platform.resource.compute.runtime import InMemoryComputeInventory, InMemoryComputeScheduler
from research_platform.resource.lease.api import ResourceLeasePort, ResourceOwnershipPort
from research_platform.resource.lease.runtime import InMemoryResourceLeaseRegistry
from research_platform.environment.catalog.api import ExecutionEnvironmentCatalogPort
from research_platform.environment.catalog.runtime import ExecutionEnvironmentCatalog
from research_platform.scope.api import ScopeRegistryPort
from research_platform.scope.runtime import InMemoryScopeRegistry
from research_platform.scope.providers import SQLiteScopeRegistry
from research_platform.governance.architecture.runtime.capability_composition import (
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
    endpoint_allocations: EndpointAllocationPort
    compute_inventory: ComputeInventoryPort
    compute_scheduler: ComputeSchedulerPort


def build_in_memory_platform_meta() -> PlatformMetaAuthorities:
    scopes = InMemoryScopeRegistry()
    systems = build_default_system_registry()
    resources = InMemoryResourceLeaseRegistry()
    compute_inventory = InMemoryComputeInventory()
    endpoint_allocations = InMemoryEndpointAllocator(
        ownership=resources,
        leases=resources,
        probe=SocketEndpointProbe(),
    )
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
        endpoint_allocations=endpoint_allocations,
        compute_inventory=compute_inventory,
        compute_scheduler=InMemoryComputeScheduler(compute_inventory),
    )


def build_durable_platform_meta(root: str | Path) -> PlatformMetaAuthorities:
    """Build the production authority bundle over one durable SQLite root.

    Catalogs that are immutable project inputs remain lightweight registries;
    scope hierarchy, resource ownership/leases, and endpoint allocations share
    one SQLite authority and therefore survive process restart and coordinate
    competing workers.
    """

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    database = root / "platform-meta.sqlite"
    scopes = SQLiteScopeRegistry(database)
    systems = build_default_system_registry()
    resources = SQLiteResourceLeaseRegistry(database)
    endpoint_allocations = AtomicEndpointAllocator(
        reservations=SQLiteEndpointAllocationStore(database),
        probe=SocketEndpointProbe(),
    )
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
        endpoint_allocations=endpoint_allocations,
        compute_inventory=compute_inventory,
        compute_scheduler=InMemoryComputeScheduler(compute_inventory),
    )


__all__ = ["PlatformMetaAuthorities", "build_durable_platform_meta", "build_in_memory_platform_meta"]
