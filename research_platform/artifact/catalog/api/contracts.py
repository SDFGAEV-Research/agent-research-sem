from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from research_platform.scope.api import ScopeIdentity


class ArtifactKind(StrEnum):
    SCIENTIFIC = "scientific"
    RUNTIME = "runtime"
    DIAGNOSTIC = "diagnostic"
    DATASET = "dataset"
    MODEL = "model"
    CHECKPOINT = "checkpoint"
    REPORT = "report"
    PUBLICATION = "publication"


class ArtifactRetention(StrEnum):
    EPHEMERAL = "ephemeral"
    RUN = "run"
    PROJECT = "project"
    RELEASE = "release"
    PERMANENT = "permanent"


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    kind: ArtifactKind
    scope: ScopeIdentity
    digest: str
    location: str
    producer_component_id: str
    producer_operation_id: str | None = None
    media_type: str = "application/octet-stream"
    lineage: tuple[str, ...] = ()
    retention: ArtifactRetention = ArtifactRetention.PROJECT
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.digest.strip() or not self.location.strip():
            raise ValueError("artifact identity, digest and location must be non-empty")
        if not self.producer_component_id.strip():
            raise ValueError("artifact producer_component_id must be non-empty")


@dataclass(frozen=True, slots=True)
class ArtifactQuery:
    scope: ScopeIdentity | None = None
    kind: ArtifactKind | None = None
    producer_component_id: str | None = None


__all__ = ["ArtifactKind", "ArtifactQuery", "ArtifactRecord", "ArtifactRetention"]
