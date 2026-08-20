from __future__ import annotations

import hashlib
from typing import Iterator

from research_platform.platform.kernel import canonical_bytes
from .evidence_api import EvidenceCut, EvidenceReadPort, EvidenceRecord, EvidenceSnapshot, EvidenceSnapshotPort, EvidenceStorePort


_EMPTY_CHAIN_DIGEST = hashlib.sha256().hexdigest()


def build_evidence_record(evidence_id: str, sequence: int, payload: object) -> EvidenceRecord:
    """Build one canonical J_mem record without binding callers to the storage backend."""
    encoded = canonical_bytes(payload)
    return EvidenceRecord(evidence_id, sequence, payload, hashlib.sha256(encoded).hexdigest())


def _row_chain_bytes(row: EvidenceRecord, *, first: bool) -> bytes:
    prefix = b"" if first else b"\n"
    return prefix + f"{row.sequence}:{row.evidence_id}:{row.digest}".encode("utf-8")


class InMemoryEvidenceReadView(EvidenceReadPort):
    """Pinned append-only read view over the in-memory J_mem backend."""

    __slots__ = ("_rows", "_index", "_prefix_digests", "_count", "sequence", "digest")

    def __init__(
        self,
        rows: list[EvidenceRecord],
        index: dict[str, int],
        prefix_digests: list[str],
        *,
        count: int,
        sequence: int,
        digest: str,
    ) -> None:
        self._rows = rows
        self._index = index
        self._prefix_digests = prefix_digests
        self._count = count
        self.sequence = sequence
        self.digest = digest

    @property
    def count(self) -> int:
        return self._count

    def latest(self) -> EvidenceRecord | None:
        return None if self._count == 0 else self._rows[self._count - 1]

    def contains(self, evidence_id: str) -> bool:
        position = self._index.get(evidence_id)
        return position is not None and position < self._count

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        position = self._index.get(evidence_id)
        if position is None or position >= self._count:
            return None
        return self._rows[position]

    def sequence_of(self, evidence_id: str) -> int | None:
        row = self.get(evidence_id)
        return None if row is None else row.sequence

    def prefix_digest(self, count: int) -> str:
        if count < 0 or count > self._count:
            raise ValueError("evidence prefix count outside pinned view")
        return _EMPTY_CHAIN_DIGEST if count == 0 else self._prefix_digests[count - 1]

    def iter_rows(self, start_position: int = 0) -> Iterator[EvidenceRecord]:
        if start_position < 0 or start_position > self._count:
            raise ValueError("evidence start position outside pinned view")
        for position in range(start_position, self._count):
            yield self._rows[position]

    def materialize(self) -> EvidenceSnapshot:
        return EvidenceSnapshot(self.sequence, tuple(self._rows[: self._count]), self.digest)


class InMemoryEvidenceStore(EvidenceStorePort):
    """Append-only J_mem authority; retrieval-scoring/index algorithms live elsewhere."""

    def __init__(self) -> None:
        self._rows: list[EvidenceRecord] = []
        self._index: dict[str, int] = {}
        self._prefix_digests: list[str] = []
        self._chain_hasher = hashlib.sha256()

    @classmethod
    def from_snapshot(cls, snapshot: EvidenceSnapshot) -> "InMemoryEvidenceStore":
        store = cls()
        for row in snapshot.rows:
            store.append(row)
        rebuilt = store.cut()
        if rebuilt.sequence != snapshot.sequence or rebuilt.digest != snapshot.digest:
            raise ValueError("J_mem snapshot sequence/digest mismatch")
        return store

    def append_payload(self, evidence_id: str, sequence: int, payload: object) -> EvidenceRecord:
        row = build_evidence_record(evidence_id, sequence, payload)
        self._append_validated(row)
        return row

    def append(self, row: EvidenceRecord) -> None:
        if row.digest != build_evidence_record(row.evidence_id, row.sequence, row.payload).digest:
            raise ValueError("J_mem evidence digest mismatch")
        self._append_validated(row)

    def _append_validated(self, row: EvidenceRecord) -> None:
        if self._rows and row.sequence <= self._rows[-1].sequence:
            raise ValueError("J_mem sequence must increase")
        if row.evidence_id in self._index:
            raise ValueError("duplicate J_mem evidence_id")
        position = len(self._rows)
        self._chain_hasher.update(_row_chain_bytes(row, first=not self._rows))
        self._index[row.evidence_id] = position
        self._rows.append(row)
        self._prefix_digests.append(self._chain_hasher.hexdigest())

    def cut(self) -> EvidenceCut:
        return EvidenceCut(
            sequence=self._rows[-1].sequence if self._rows else 0,
            count=len(self._rows),
            digest=self._chain_hasher.hexdigest(),
        )

    def read_view(self) -> EvidenceReadPort:
        cut = self.cut()
        return InMemoryEvidenceReadView(
            self._rows,
            self._index,
            self._prefix_digests,
            count=cut.count,
            sequence=cut.sequence,
            digest=cut.digest,
        )

    def snapshot(self) -> EvidenceSnapshot:
        return self.read_view().materialize()

    def restore(self, snapshot: EvidenceSnapshot) -> None:
        rebuilt = type(self).from_snapshot(snapshot)
        self._rows = rebuilt._rows
        self._index = rebuilt._index
        self._prefix_digests = rebuilt._prefix_digests
        self._chain_hasher = rebuilt._chain_hasher


class InMemoryEvidenceSnapshotSource(EvidenceSnapshotPort):
    """Read-only canonical snapshot source for clean materialization."""

    def __init__(self, store: InMemoryEvidenceStore) -> None:
        self._store = store

    def snapshot(self) -> EvidenceSnapshot:
        return self._store.snapshot()


__all__ = ["InMemoryEvidenceReadView", "InMemoryEvidenceSnapshotSource", "InMemoryEvidenceStore", "build_evidence_record"]
