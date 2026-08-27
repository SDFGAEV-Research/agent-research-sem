from __future__ import annotations

from dataclasses import replace
from threading import RLock

from research_platform.resource.allocation.api import (
    AtomicEndpointReservationPort,
    DEFAULT_ENDPOINT_LEASE_POLICY,
    EndpointAllocation,
    EndpointAllocationRequest,
    EndpointAllocationState,
    EndpointAllocationPort,
    EndpointProbePort,
    EndpointReservationStatus,
)
from research_platform.resource.lease.api import (
    ResourceLease,
    ResourceLeasePort,
    ResourceOwner,
    ResourceOwnershipPort,
)


class EndpointAllocationConflict(RuntimeError):
    pass


class EndpointAllocationUnavailable(RuntimeError):
    def __init__(self, request: EndpointAllocationRequest, attempts: tuple[str, ...]) -> None:
        self.request = request
        self.attempts = attempts
        detail = "; ".join(attempts) if attempts else "no candidates"
        super().__init__(f"no endpoint candidate is allocatable for {request.allocation_id}: {detail}")


class AtomicEndpointAllocator(EndpointAllocationPort):
    """Provider-neutral endpoint allocation policy over one atomic reservation authority.

    Candidate order and OS probing are runtime policy. Ownership, lease fencing and
    allocation persistence are committed by ``AtomicEndpointReservationPort`` as one
    transaction. This keeps the allocator independent of SQLite while preventing the
    old lease-then-allocation split-transaction leak.
    """

    def __init__(
        self,
        *,
        reservations: AtomicEndpointReservationPort,
        probe: EndpointProbePort,
        lease_ttl_seconds: float = DEFAULT_ENDPOINT_LEASE_POLICY.ttl_seconds,
    ) -> None:
        if lease_ttl_seconds <= 0:
            raise ValueError("endpoint lease_ttl_seconds must be > 0")
        self._reservations = reservations
        self._probe = probe
        self._lease_ttl_seconds = float(lease_ttl_seconds)

    def allocate(self, request: EndpointAllocationRequest) -> EndpointAllocation:
        request_digest = request.digest()
        existing = self._reservations.get(request.allocation_id)
        if existing is not None:
            return self._resolve_existing(request, request_digest, existing)

        attempts: list[str] = []
        for endpoint in request.candidates():
            probe = self._probe.probe(endpoint)
            if not probe.available:
                attempts.append(f"{endpoint.key}:probe:{probe.reason}")
                continue

            lease_id = f"endpoint:{request.allocation_id}:{endpoint.key}"
            result = self._reservations.reserve(
                owner=ResourceOwner(endpoint.resource, request.owner_scope, request.ownership),
                lease=ResourceLease(
                    lease_id=lease_id,
                    resource=endpoint.resource,
                    holder_scope=request.holder_scope,
                    purpose=request.purpose,
                ),
                allocation=EndpointAllocation(
                    allocation_id=request.allocation_id,
                    endpoint=endpoint,
                    lease_id=lease_id,
                    holder_scope=request.holder_scope,
                    purpose=request.purpose,
                    request_digest=request_digest,
                ),
                ttl_seconds=self._lease_ttl_seconds,
            )
            if result.status is EndpointReservationStatus.RESERVED:
                assert result.allocation is not None
                return result.allocation
            if result.status is EndpointReservationStatus.EXISTING:
                assert result.allocation is not None
                return self._resolve_existing(request, request_digest, result.allocation)
            if result.status is EndpointReservationStatus.RESOURCE_BUSY:
                attempts.append(f"{endpoint.key}:lease-active")
                continue
            if result.status is EndpointReservationStatus.OWNER_CONFLICT:
                attempts.append(f"{endpoint.key}:owner-conflict")
                continue
            attempts.append(f"{endpoint.key}:reservation:{result.status.value}")

        raise EndpointAllocationUnavailable(request, tuple(attempts))

    @staticmethod
    def _resolve_existing(
        request: EndpointAllocationRequest,
        request_digest: str,
        existing: EndpointAllocation,
    ) -> EndpointAllocation:
        if existing.request_digest != request_digest:
            raise EndpointAllocationConflict(request.allocation_id)
        if existing.state is EndpointAllocationState.ACTIVE:
            return existing
        raise EndpointAllocationConflict(
            f"endpoint allocation was already released: {request.allocation_id}"
        )

    def renew(self, allocation_id: str, *, ttl_seconds: float | None = None) -> EndpointAllocation:
        ttl = self._lease_ttl_seconds if ttl_seconds is None else float(ttl_seconds)
        if ttl <= 0:
            raise ValueError("endpoint lease ttl_seconds must be > 0")
        return self._reservations.renew(allocation_id, ttl_seconds=ttl)

    def renew_many(self, allocation_ids: tuple[str, ...], *, ttl_seconds: float | None = None) -> tuple[EndpointAllocation, ...]:
        if not allocation_ids:
            return ()
        if len(set(allocation_ids)) != len(allocation_ids):
            raise ValueError("endpoint allocation ids must be unique")
        ttl = self._lease_ttl_seconds if ttl_seconds is None else float(ttl_seconds)
        if ttl <= 0:
            raise ValueError("endpoint lease ttl_seconds must be > 0")
        return self._reservations.renew_many(allocation_ids, ttl_seconds=ttl)

    def release(self, allocation_id: str) -> EndpointAllocation:
        return self._reservations.release(allocation_id)

    def get(self, allocation_id: str) -> EndpointAllocation:
        current = self._reservations.get(allocation_id)
        if current is None:
            raise KeyError(allocation_id)
        return current

    def active(self) -> tuple[EndpointAllocation, ...]:
        return self._reservations.active()


class InMemoryEndpointAllocator(EndpointAllocationPort):
    """Deterministic in-process allocator over injected lease/probe authorities.

    This implementation is intentionally independent from the durable atomic
    reservation authority. Its single process lock gives the in-memory composition
    one transaction boundary while the durable composition uses
    :class:`AtomicEndpointAllocator`.
    """

    def __init__(
        self,
        *,
        ownership: ResourceOwnershipPort,
        leases: ResourceLeasePort,
        probe: EndpointProbePort,
        lease_ttl_seconds: float = DEFAULT_ENDPOINT_LEASE_POLICY.ttl_seconds,
    ) -> None:
        if lease_ttl_seconds <= 0:
            raise ValueError("endpoint lease_ttl_seconds must be > 0")
        self._ownership = ownership
        self._leases = leases
        self._probe = probe
        self._lease_ttl_seconds = float(lease_ttl_seconds)
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
            request_digest = request.digest()
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
                    granted = self._leases.acquire(
                        ResourceLease(
                            lease_id=lease_id,
                            resource=resource,
                            holder_scope=request.holder_scope,
                            purpose=request.purpose,
                        ),
                        ttl_seconds=self._lease_ttl_seconds,
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
                    request_digest=request_digest,
                    lease_holder_generation=granted.holder_generation,
                    lease_fencing_token=granted.fencing_token,
                    lease_expires_at_epoch_s=granted.expires_at_epoch_s,
                )
                self._allocations[request.allocation_id] = allocation
                return allocation
            raise EndpointAllocationUnavailable(request, tuple(attempts))

    def renew(self, allocation_id: str, *, ttl_seconds: float | None = None) -> EndpointAllocation:
        with self._lock:
            current = self.get(allocation_id)
            if current.state is not EndpointAllocationState.ACTIVE:
                raise EndpointAllocationConflict(f"endpoint allocation is not active: {allocation_id}")
            ttl = self._lease_ttl_seconds if ttl_seconds is None else float(ttl_seconds)
            granted = self._leases.renew(
                current.lease_id,
                fencing_token=current.lease_fencing_token,
                ttl_seconds=ttl,
            )
            updated = replace(
                current,
                lease_holder_generation=granted.holder_generation,
                lease_fencing_token=granted.fencing_token,
                lease_expires_at_epoch_s=granted.expires_at_epoch_s,
            )
            self._allocations[allocation_id] = updated
            return updated

    def renew_many(self, allocation_ids: tuple[str, ...], *, ttl_seconds: float | None = None) -> tuple[EndpointAllocation, ...]:
        if not allocation_ids:
            return ()
        if len(set(allocation_ids)) != len(allocation_ids):
            raise ValueError("endpoint allocation ids must be unique")
        with self._lock:
            return tuple(self.renew(allocation_id, ttl_seconds=ttl_seconds) for allocation_id in allocation_ids)

    def release(self, allocation_id: str) -> EndpointAllocation:
        with self._lock:
            current = self.get(allocation_id)
            if current.state is EndpointAllocationState.RELEASED:
                return current
            self._leases.release(current.lease_id)
            released = replace(current, state=EndpointAllocationState.RELEASED)
            self._allocations[allocation_id] = released
            return released

    def get(self, allocation_id: str) -> EndpointAllocation:
        try:
            return self._allocations[allocation_id]
        except KeyError as exc:
            raise KeyError(allocation_id) from exc

    def active(self) -> tuple[EndpointAllocation, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (row for row in self._allocations.values() if row.state is EndpointAllocationState.ACTIVE),
                    key=lambda row: row.allocation_id,
                )
            )


__all__ = [
    "AtomicEndpointAllocator",
    "EndpointAllocationConflict",
    "EndpointAllocationUnavailable",
    "InMemoryEndpointAllocator",
]
