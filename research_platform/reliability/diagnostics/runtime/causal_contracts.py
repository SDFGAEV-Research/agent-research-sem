from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CausalNode:
    node_id: str
    kind: str
    attrs: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CausalEdge:
    source: str
    relation: str
    target: str


@dataclass(frozen=True, slots=True)
class CausalGraphSnapshot:
    root_id: str
    nodes: tuple[dict[str, object], ...]
    edges: tuple[dict[str, str], ...]


__all__ = ["CausalEdge", "CausalGraphSnapshot", "CausalNode"]
