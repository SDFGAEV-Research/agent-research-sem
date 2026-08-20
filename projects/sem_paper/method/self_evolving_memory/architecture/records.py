from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class NodePartitionedRecord:
    """One typed method-memory record already assigned to an architecture node."""

    node_id: str
    record_id: str
    sequence: int
    text: str
    payload: Mapping[str, object]
    source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.node_id, self.record_id)):
            raise ValueError("node-partitioned record identity is required")
        if self.sequence < 0:
            raise ValueError("node-partitioned record sequence must be non-negative")
        if not isinstance(self.payload, Mapping):
            raise TypeError("node-partitioned record payload must be a mapping")


__all__ = ["NodePartitionedRecord"]
