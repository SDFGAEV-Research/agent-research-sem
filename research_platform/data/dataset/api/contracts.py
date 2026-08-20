from __future__ import annotations
from dataclasses import dataclass
from research_platform.scope.api import ScopeIdentity

@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    dataset_id: str
    version: str
    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.version.strip(): raise ValueError("dataset identity/version must be non-empty")
    @property
    def key(self) -> str: return f"{self.dataset_id}@{self.version}"

@dataclass(frozen=True, slots=True)
class DatasetVersion:
    identity: DatasetIdentity
    scope: ScopeIdentity
    digest: str
    location: str
    schema_ref: str | None = None
    parent_versions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()
    def __post_init__(self) -> None:
        if not self.digest.strip() or not self.location.strip(): raise ValueError("dataset digest/location must be non-empty")

@dataclass(frozen=True, slots=True)
class DatasetQuery:
    dataset_id: str | None = None
    scope: ScopeIdentity | None = None
    tag: str | None = None

__all__ = ["DatasetIdentity", "DatasetQuery", "DatasetVersion"]
