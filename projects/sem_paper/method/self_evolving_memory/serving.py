from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from typing import Iterator, Protocol
from research_platform.platform.kernel import JsonValue


@dataclass(frozen=True, slots=True)
class MemoryNodeDocument:
    node_id: str
    sequence: int
    digest: str
    text: str


class MemoryReadSnapshot(Protocol):
    """Pinned raw memory read surface; retrieval algorithms own their derived indexes."""

    @property
    def generation(self) -> str: ...
    @property
    def node_count(self) -> int: ...
    def latest_node_id(self) -> str | None: ...
    def contains(self, node_id: str) -> bool: ...
    def node_ids(self) -> tuple[str, ...]: ...
    def node_sequence(self, node_id: str) -> int | None: ...
    def prefix_digest(self, count: int) -> str: ...
    def iter_node_documents(self, start_position: int = 0) -> Iterator[MemoryNodeDocument]: ...
    def resolve(self, node_ids: tuple[str, ...]) -> tuple[tuple[str, str], ...]: ...


class MemorySnapshotProvider(Protocol):
    def open_snapshot(self) -> MemoryReadSnapshot: ...


class QueryPlanner(Protocol):
    def plan(self, intent: str, snapshot: MemoryReadSnapshot, *, limit: int) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class ServingResult:
    generation: str
    context_text: str
    selected_nodes: tuple[str, ...]
    diagnostic_records: tuple["MemoryServingRecord", ...] = ()


@dataclass(frozen=True, slots=True)
class MemoryServingRecord:
    """Provider-neutral facts needed by the session diagnostic adapter.

    This value is deliberately owned by serving rather than evolution. A
    serving provider reports what it returned; the evolution diagnostic plane
    decides how (or whether) to interpret those facts.
    """

    node_id: str
    record_id: str
    score: float
    payload: Mapping[str, JsonValue] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.record_id.strip():
            raise ValueError("serving diagnostic record identity is required")
        if not math.isfinite(float(self.score)):
            raise ValueError("serving diagnostic record score must be finite")
        if not isinstance(self.payload, Mapping):
            raise TypeError("serving diagnostic record payload must be a mapping")
        if any(
            not isinstance(ref, str) or not ref.strip() for ref in self.source_refs
        ):
            raise ValueError("serving diagnostic source refs must be non-empty")
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("serving diagnostic source refs must be unique")


class MemoryServingService:
    """Plan against a pinned snapshot, materialize only the records actually selected."""

    def __init__(self, snapshots: MemorySnapshotProvider, planner: QueryPlanner) -> None:
        self.snapshots = snapshots
        self.planner = planner

    def recall(self, intent: str, *, limit: int) -> ServingResult:
        if limit <= 0:
            raise ValueError("memory recall limit must be positive")
        snapshot = self.snapshots.open_snapshot()
        nodes = self.planner.plan(intent, snapshot, limit=limit)
        if len(nodes) > limit:
            raise ValueError("query planner exceeded recall limit")
        if len(nodes) != len(set(nodes)):
            raise ValueError("query planner selected duplicate nodes")
        if any(not snapshot.contains(node_id) for node_id in nodes):
            raise ValueError("query planner selected node outside pinned generation")
        records = snapshot.resolve(nodes)
        record_map = dict(records)
        if any(node_id not in record_map for node_id in nodes):
            raise ValueError("pinned memory snapshot failed to resolve selected node")
        text = "\n".join(record_map[node_id] for node_id in nodes)
        return ServingResult(
            snapshot.generation,
            text,
            nodes,
            tuple(
                MemoryServingRecord(
                    node_id=node_id,
                    record_id=node_id,
                    # The raw serving ABI exposes selection but no calibrated
                    # rank score. A resolved selected row is therefore a
                    # positive binary observation, not a fabricated rank.
                    score=1.0,
                    payload={"text": record_map[node_id]},
                    source_refs=(node_id,),
                )
                for node_id in nodes
            ),
        )


__all__ = [
    "MemoryNodeDocument",
    "MemoryReadSnapshot",
    "MemoryServingRecord",
    "MemoryServingService",
    "MemorySnapshotProvider",
    "QueryPlanner",
    "ServingResult",
]
