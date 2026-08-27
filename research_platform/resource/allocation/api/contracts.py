from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.platform.kernel import canonical_digest
from research_platform.resource.lease.api import (
    ResourceIdentity,
    ResourceKind,
    ResourceLease,
    ResourceOwnership,
)
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity


class EndpointProtocol(StrEnum):
    TCP = "tcp"
    UDP = "udp"


class EndpointAllocationState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class EndpointReservationStatus(StrEnum):
    RESERVED = "reserved"
    EXISTING = "existing"
    RESOURCE_BUSY = "resource-busy"
    OWNER_CONFLICT = "owner-conflict"


@dataclass(frozen=True, slots=True, order=True)
class NetworkEndpoint:
    """An address that can be exclusively attached to one service instance."""

    host: str
    port: int
    protocol: EndpointProtocol = EndpointProtocol.TCP

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("network endpoint host is required")
        if not 1 <= self.port <= 65535:
            raise ValueError("network endpoint port must be between 1 and 65535")

    @property
    def key(self) -> str:
        return f"{self.protocol.value}://{self.host.casefold()}:{self.port}"

    @property
    def resource(self) -> ResourceIdentity:
        return ResourceIdentity(ResourceKind.NETWORK_ENDPOINT, self.key)


@dataclass(frozen=True, slots=True)
class EndpointAllocationRequest:
    allocation_id: str
    holder_scope: ScopeIdentity
    purpose: str
    host: str
    candidate_ports: tuple[int, ...]
    protocol: EndpointProtocol = EndpointProtocol.TCP
    owner_scope: ScopeIdentity = PLATFORM_SCOPE
    ownership: ResourceOwnership = ResourceOwnership.EXTERNAL

    def __post_init__(self) -> None:
        if not self.allocation_id.strip() or not self.purpose.strip() or not self.host.strip():
            raise ValueError("endpoint allocation identity, purpose and host are required")
        if not self.candidate_ports:
            raise ValueError("endpoint allocation requires explicit candidate ports")
        if len(set(self.candidate_ports)) != len(self.candidate_ports):
            raise ValueError("endpoint allocation candidate ports must be unique")
        if any(not 1 <= port <= 65535 for port in self.candidate_ports):
            raise ValueError("endpoint allocation candidate ports must be between 1 and 65535")

    def candidates(self) -> tuple[NetworkEndpoint, ...]:
        return tuple(NetworkEndpoint(self.host, port, self.protocol) for port in self.candidate_ports)

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class EndpointLeasePolicy:
    """Lifecycle policy shared by endpoint allocation and lease renewal guards."""

    ttl_seconds: float = 120.0
    renewal_interval_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.ttl_seconds <= 0:
            raise ValueError("endpoint lease ttl_seconds must be > 0")
        if self.renewal_interval_seconds <= 0:
            raise ValueError("endpoint lease renewal_interval_seconds must be > 0")
        if self.renewal_interval_seconds >= self.ttl_seconds:
            raise ValueError("endpoint lease renewal interval must be shorter than ttl")


DEFAULT_ENDPOINT_LEASE_POLICY = EndpointLeasePolicy()


@dataclass(frozen=True, slots=True)
class EndpointProbeResult:
    endpoint: NetworkEndpoint
    available: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("endpoint probe reason is required")


@dataclass(frozen=True, slots=True)
class EndpointAllocation:
    allocation_id: str
    endpoint: NetworkEndpoint
    lease_id: str
    holder_scope: ScopeIdentity
    purpose: str
    request_digest: str
    state: EndpointAllocationState = EndpointAllocationState.ACTIVE
    lease_holder_generation: int = 1
    lease_fencing_token: int = 1
    lease_expires_at_epoch_s: float | None = None

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.allocation_id,
                self.lease_id,
                self.purpose,
                self.request_digest,
            )
        ):
            raise ValueError("endpoint allocation identity is incomplete")
        if self.lease_holder_generation < 1 or self.lease_fencing_token < 1:
            raise ValueError("endpoint allocation lease generation/fencing must be >= 1")


@dataclass(frozen=True, slots=True)
class EndpointReservationResult:
    status: EndpointReservationStatus
    allocation: EndpointAllocation | None = None
    lease: ResourceLease | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status in (EndpointReservationStatus.RESERVED, EndpointReservationStatus.EXISTING):
            if self.allocation is None:
                raise ValueError("successful endpoint reservation requires allocation")
        elif self.allocation is not None:
            raise ValueError("unsuccessful endpoint reservation cannot carry allocation")


__all__ = [
    "EndpointAllocation",
    "EndpointAllocationRequest",
    "EndpointAllocationState",
    "EndpointLeasePolicy",
    "DEFAULT_ENDPOINT_LEASE_POLICY",
    "EndpointReservationResult",
    "EndpointReservationStatus",
    "EndpointProbeResult",
    "EndpointProtocol",
    "NetworkEndpoint",
]
