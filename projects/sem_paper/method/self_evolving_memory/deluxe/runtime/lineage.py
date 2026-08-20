from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ..api import LineageEdge, MemoryLineageRecord


@dataclass(slots=True)
class MemoryLineageGraph:
    """Rebuildable derived lineage over current project memory records."""

    outgoing: dict[str, set[str]] = field(default_factory=dict)
    incoming: dict[str, set[str]] = field(default_factory=dict)
    relation: dict[tuple[str, str], str] = field(default_factory=dict)

    def add_record(self, record: MemoryLineageRecord) -> None:
        for source_ref in record.source_refs:
            self.outgoing.setdefault(source_ref, set()).add(record.record_id)
            self.incoming.setdefault(record.record_id, set()).add(source_ref)
            self.relation[(source_ref, record.record_id)] = "DERIVED_FROM"

    def rebuild(self, store: Mapping[str, Sequence[MemoryLineageRecord]]) -> None:
        self.outgoing.clear()
        self.incoming.clear()
        self.relation.clear()
        for records in store.values():
            for record in records:
                self.add_record(record)

    def edges(self) -> tuple[LineageEdge, ...]:
        return tuple(
            LineageEdge(source, derived, self.relation[(source, derived)])
            for source, derived in sorted(self.relation)
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "edges": [
                {"source_ref": edge.source_ref, "derived_ref": edge.derived_ref, "relation": edge.relation}
                for edge in self.edges()
            ]
        }


__all__ = ["MemoryLineageGraph"]
