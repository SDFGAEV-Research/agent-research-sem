from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol


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
        return ServingResult(snapshot.generation, text, nodes)
