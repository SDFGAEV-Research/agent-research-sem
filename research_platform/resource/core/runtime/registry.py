from __future__ import annotations

from dataclasses import replace

from research_platform.resource.core.api import LeaseState, ResourceIdentity, ResourceLease, ResourceOwner


class ResourceOwnershipConflict(RuntimeError):
    pass


class ResourceLeaseConflict(RuntimeError):
    pass


class InMemoryResourceRegistry:
    """Authority for generic resource ownership and leases; resource-specific state stays elsewhere."""

    def __init__(self) -> None:
        self._owners: dict[ResourceIdentity, ResourceOwner] = {}
        self._leases: dict[str, ResourceLease] = {}

    def register_owner(self, owner: ResourceOwner) -> None:
        existing = self._owners.get(owner.resource)
        if existing is not None and existing != owner:
            raise ResourceOwnershipConflict(owner.resource.key)
        self._owners[owner.resource] = owner

    def owner(self, resource: ResourceIdentity) -> ResourceOwner:
        try:
            return self._owners[resource]
        except KeyError as exc:
            raise KeyError(resource.key) from exc

    def remove_owner(self, resource: ResourceIdentity) -> None:
        if self.active_for(resource):
            raise ResourceOwnershipConflict(f"resource has active leases: {resource.key}")
        self._owners.pop(resource, None)

    def acquire(self, lease: ResourceLease) -> None:
        if lease.resource not in self._owners:
            raise KeyError(lease.resource.key)
        existing = self._leases.get(lease.lease_id)
        if existing is not None and existing != lease:
            raise ResourceLeaseConflict(lease.lease_id)
        self._leases[lease.lease_id] = lease

    def release(self, lease_id: str) -> ResourceLease:
        current = self.get(lease_id)
        if current.state is LeaseState.RELEASED:
            return current
        released = replace(current, state=LeaseState.RELEASED)
        self._leases[lease_id] = released
        return released

    def get(self, lease_id: str) -> ResourceLease:
        try:
            return self._leases[lease_id]
        except KeyError as exc:
            raise KeyError(lease_id) from exc

    def active_for(self, resource: ResourceIdentity) -> tuple[ResourceLease, ...]:
        return tuple(sorted(
            (lease for lease in self._leases.values() if lease.resource == resource and lease.state is LeaseState.ACTIVE),
            key=lambda lease: lease.lease_id,
        ))


__all__ = ["InMemoryResourceRegistry", "ResourceLeaseConflict", "ResourceOwnershipConflict"]
