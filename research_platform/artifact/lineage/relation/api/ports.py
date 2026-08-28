from __future__ import annotations

from typing import Protocol, runtime_checkable

from .contracts import ArtifactLineageEdge


@runtime_checkable
class ArtifactLineageRelationPort(Protocol):
    """Append-only provenance relation authority; never scientific-result truth."""

    def add(self, edge: ArtifactLineageEdge) -> ArtifactLineageEdge: ...
    def parents(self, child_artifact_id: str) -> tuple[ArtifactLineageEdge, ...]: ...
    def children(self, parent_artifact_id: str) -> tuple[ArtifactLineageEdge, ...]: ...


__all__ = ["ArtifactLineageRelationPort"]
