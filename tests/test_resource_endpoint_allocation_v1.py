from __future__ import annotations

import pytest

from research_platform.resource.allocation.api import (
    EndpointAllocationRequest,
    EndpointProbeResult,
    NetworkEndpoint,
)
from research_platform.resource.allocation.runtime import (
    EndpointAllocationUnavailable,
    InMemoryEndpointAllocator,
)
from research_platform.resource.lease.api import ResourceIdentity, ResourceKind
from research_platform.resource.lease.runtime import InMemoryResourceLeaseRegistry
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind


class ScriptedProbe:
    def __init__(self, unavailable: set[int] = set()) -> None:
        self.unavailable = unavailable
        self.seen: list[int] = []

    def probe(self, endpoint: NetworkEndpoint) -> EndpointProbeResult:
        self.seen.append(endpoint.port)
        return EndpointProbeResult(
            endpoint,
            endpoint.port not in self.unavailable,
            "scripted-unavailable" if endpoint.port in self.unavailable else "scripted-available",
        )


def _request(allocation_id: str, ports: tuple[int, ...]) -> EndpointAllocationRequest:
    return EndpointAllocationRequest(
        allocation_id=allocation_id,
        holder_scope=ScopeIdentity(ScopeKind.BRANCH, allocation_id),
        purpose="minecraft branch server",
        host="127.0.0.1",
        candidate_ports=ports,
        owner_scope=PLATFORM_SCOPE,
    )


def test_endpoint_allocator_uses_explicit_order_and_lease_exclusivity() -> None:
    leases = InMemoryResourceLeaseRegistry()
    probe = ScriptedProbe()
    allocator = InMemoryEndpointAllocator(ownership=leases, leases=leases, probe=probe)

    first = allocator.allocate(_request("branch-a", (25565, 25566)))
    second = allocator.allocate(_request("branch-b", (25565, 25566)))

    assert first.endpoint.port == 25565
    assert second.endpoint.port == 25566
    assert probe.seen == [25565, 25566]
    assert len(leases.active_for(first.endpoint.resource)) == 1


def test_endpoint_allocator_releases_logical_lease_and_allows_reallocation() -> None:
    leases = InMemoryResourceLeaseRegistry()
    allocator = InMemoryEndpointAllocator(
        ownership=leases,
        leases=leases,
        probe=ScriptedProbe(),
    )

    first = allocator.allocate(_request("branch-a", (25565,)))
    released = allocator.release(first.allocation_id)
    assert released.state.value == "released"
    assert not leases.active_for(first.endpoint.resource)

    second = allocator.allocate(_request("branch-b", (25565,)))
    assert second.endpoint == first.endpoint


def test_endpoint_allocator_reports_probe_rejection_without_fallback() -> None:
    leases = InMemoryResourceLeaseRegistry()
    probe = ScriptedProbe({25565, 25566})
    allocator = InMemoryEndpointAllocator(ownership=leases, leases=leases, probe=probe)

    with pytest.raises(EndpointAllocationUnavailable) as raised:
        allocator.allocate(_request("branch-a", (25565, 25566)))

    assert raised.value.attempts == (
        "tcp://127.0.0.1:25565:probe:scripted-unavailable",
        "tcp://127.0.0.1:25566:probe:scripted-unavailable",
    )


def test_resource_lease_registry_rejects_two_active_leases_for_one_resource() -> None:
    registry = InMemoryResourceLeaseRegistry()
    resource = ResourceIdentity(ResourceKind.STORAGE, "artifact-pool")
    from research_platform.resource.lease.api import ResourceLease, ResourceOwner

    registry.register_owner(ResourceOwner(resource, PLATFORM_SCOPE))
    registry.acquire(ResourceLease("lease-a", resource, PLATFORM_SCOPE, "first"))
    with pytest.raises(RuntimeError):
        registry.acquire(ResourceLease("lease-b", resource, PLATFORM_SCOPE, "second"))
