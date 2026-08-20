from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.scope.api import ScopeIdentity


class ResourceKind(StrEnum):
    STORAGE = "storage"
    WORKSPACE = "workspace"
    EXECUTION_ENVIRONMENT = "execution-environment"
    MODEL_ASSET = "model-asset"
    COMPUTE = "compute"
    GPU = "gpu"
    DATASET = "dataset"
    CACHE = "cache"


class ResourceOwnership(StrEnum):
    PLATFORM_MANAGED = "platform-managed"
    EXTERNAL = "external"
    SHARED = "shared"


class LeaseState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


@dataclass(frozen=True, slots=True, order=True)
class ResourceIdentity:
    kind: ResourceKind
    resource_id: str

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise ValueError("resource_id must be non-empty")

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.resource_id}"


@dataclass(frozen=True, slots=True)
class ResourceOwner:
    resource: ResourceIdentity
    scope: ScopeIdentity
    ownership: ResourceOwnership = ResourceOwnership.PLATFORM_MANAGED


@dataclass(frozen=True, slots=True)
class ResourceLease:
    lease_id: str
    resource: ResourceIdentity
    holder_scope: ScopeIdentity
    purpose: str
    state: LeaseState = LeaseState.ACTIVE

    def __post_init__(self) -> None:
        if not self.lease_id.strip() or not self.purpose.strip():
            raise ValueError("lease identity and purpose must be non-empty")


__all__ = [
    "LeaseState",
    "ResourceIdentity",
    "ResourceKind",
    "ResourceLease",
    "ResourceOwner",
    "ResourceOwnership",
]
