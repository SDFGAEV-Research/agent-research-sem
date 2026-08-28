from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

from research_platform.platform.kernel import JsonValue


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    sequence: int
    payload: JsonValue
    digest: str


@dataclass(frozen=True, slots=True)
class EvidenceCut:
    sequence: int
    count: int
    digest: str


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    sequence: int
    rows: tuple[EvidenceRecord, ...]
    digest: str


class EvidenceReadPort(Protocol):
    """Pinned canonical evidence read surface independent of physical storage/retrieval algorithm."""

    @property
    def sequence(self) -> int: ...

    @property
    def digest(self) -> str: ...

    @property
    def count(self) -> int: ...

    def latest(self) -> EvidenceRecord | None: ...
    def contains(self, evidence_id: str) -> bool: ...
    def get(self, evidence_id: str) -> EvidenceRecord | None: ...
    def sequence_of(self, evidence_id: str) -> int | None: ...
    def prefix_digest(self, count: int) -> str: ...
    def iter_rows(self, start_position: int = 0) -> Iterator[EvidenceRecord]: ...
    def materialize(self) -> EvidenceSnapshot: ...


class EvidenceMaterializationSource(Protocol):
    """Source that atomically pins one canonical evidence cut for materialization."""

    def pin(self) -> EvidenceReadPort: ...


class EvidenceStorePort(EvidenceMaterializationSource, Protocol):
    """Mutable canonical J_mem authority independent of physical storage."""

    def append_payload(self, evidence_id: str, sequence: int, payload: JsonValue) -> EvidenceRecord: ...
    def cut(self) -> EvidenceCut: ...
    def pin(self) -> EvidenceReadPort: ...
    def read_view(self) -> EvidenceReadPort: ...
    def snapshot(self) -> EvidenceSnapshot: ...
    def restore(self, snapshot: EvidenceSnapshot) -> None: ...


class EvidenceSnapshotPort(Protocol):
    """Minimal canonical snapshot source used by legacy flat materialization."""

    def snapshot(self) -> EvidenceSnapshot: ...


__all__ = [
    "EvidenceCut",
    "EvidenceMaterializationSource",
    "EvidenceReadPort",
    "EvidenceRecord",
    "EvidenceSnapshot",
    "EvidenceSnapshotPort",
    "EvidenceStorePort",
]
