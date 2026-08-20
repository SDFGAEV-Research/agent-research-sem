from __future__ import annotations

from typing import Protocol

from .contracts import ArtifactQuery, ArtifactRecord


class ArtifactRegistryPort(Protocol):
    def put(self, artifact: ArtifactRecord) -> ArtifactRecord: ...
    def get(self, artifact_id: str) -> ArtifactRecord: ...
    def query(self, query: ArtifactQuery = ArtifactQuery()) -> tuple[ArtifactRecord, ...]: ...
    def remove(self, artifact_id: str) -> bool: ...


__all__ = ["ArtifactRegistryPort"]
