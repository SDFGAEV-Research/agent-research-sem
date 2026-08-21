from __future__ import annotations

from threading import RLock

from research_platform.resource.allocation.api import (
    EndpointAllocation,
    EndpointAllocationRequest,
    EndpointAllocationState,
    EndpointAllocationPort,
    EndpointProbePort,
    NetworkEndpoint,
)
from research_platform.resource.lease.api import ResourceLease, ResourceLeasePort, ResourceOwner, ResourceOwnershipPort


class EndpointAllocationConflict(RuntimeError):
    pass


class EndpointAllocationUnavailable(RuntimeError):
    def __init__(self, request: EndpointAllocationRequest, attempts: tuple[str, ...]) -> None:
        self.request = request
        self.attempts = attempts
        detail = "; ".join(attempts) if attempts else "no candidates"
        super().__init__(f"no endpoint candidate is allocatable for {request.allocation_id}: {detail}")


class InMemoryEndpointAllocator(EndpointAllocationPort):
    """Deterministic endpoint allocator over injected lease and probe authorities.

    The allocator never invents a port. Candidates are tried in the exact
    order supplied by the caller; logical leases and the OS probe are both
    required before an endpoint becomes active.
    """

    def __init__(
        self,
        *,
        ownership: ResourceOwnershipPort,
        leases: ResourceLeasePort,
        probe: EndpointProbePort,
    ) -> None:
        self._ownership = ownership
        self._leases = leases
        self._probe = probe
        self._allocations: dict[str, EndpointAllocation] = {}
        self._lock = RLock()

    def allocate(self, request: EndpointAllocationRequest) -> EndpointAllocation:
        with self._lock:
            existing = self._allocations.get(request.allocation_id)
            if existing is not None:
                if existing.request_digest != request.digest():
                    raise EndpointAllocationConflict(request.allocation_id)
                if existing.state is EndpointAllocationState.ACTIVE:
                    return existing
                raise EndpointAllocationConflict(
                    f"endpoint allocation was already released: {request.allocation_id}"
                )

            attempts: list[str] = []
            for endpoint in request.candidates():
                resource = endpoint.resource
                try:
                    self._ownership.register_owner(
                        ResourceOwner(resource, request.owner_scope, request.ownership)
                    )
                except Exception as exc:
                    attempts.append(f"{endpoint.key}:owner:{type(exc).__name__}")
                    continue
                if self._leases.active_for(resource):
                    attempts.append(f"{endpoint.key}:lease-active")
                    continue
                result = self._probe.probe(endpoint)
                if not result.available:
                    attempts.append(f"{endpoint.key}:probe:{result.reason}")
                    continue
                lease_id = f"endpoint:{request.allocation_id}:{endpoint.key}"
                try:
                    self._leases.acquire(
                        ResourceLease(
                            lease_id=lease_id,
                            resource=resource,
                            holder_scope=request.holder_scope,
                            purpose=request.purpose,
                        )
                    )
                except Exception as exc:
                    attempts.append(f"{endpoint.key}:lease:{type(exc).__name__}")
                    continue
                allocation = EndpointAllocation(
                    allocation_id=request.allocation_id,
                    endpoint=endpoint,
                    lease_id=lease_id,
                    holder_scope=request.holder_scope,
                    purpose=request.purpose,
                    request_digest=request.digest(),
                )
                self._allocations[request.allocation_id] = allocation
                return allocation
            raise EndpointAllocationUnavailable(request, tuple(attempts))

    def release(self, allocation_id: str) -> EndpointAllocation:
        with self._lock:
            current = self.get(allocation_id)
            if current.state is EndpointAllocationState.RELEASED:
                return current
            self._leases.release(current.lease_id)
            released = EndpointAllocation(
                allocation_id=current.allocation_id,
                endpoint=current.endpoint,
                lease_id=current.lease_id,
                holder_scope=current.holder_scope,
                purpose=current.purpose,
                request_digest=current.request_digest,
                state=EndpointAllocationState.RELEASED,
            )
            self._allocations[allocation_id] = released
            return released

    def get(self, allocation_id: str) -> EndpointAllocation:
        try:
            return self._allocations[allocation_id]
        except KeyError as exc:
            raise KeyError(allocation_id) from exc

    def active(self) -> tuple[EndpointAllocation, ...]:
        with self._lock:
            return tuple(sorted(
                (row for row in self._allocations.values() if row.state is EndpointAllocationState.ACTIVE),
                key=lambda row: row.allocation_id,
            ))


__all__ = ["EndpointAllocationConflict", "EndpointAllocationUnavailable", "InMemoryEndpointAllocator"]
