from __future__ import annotations

from .causal_contracts import CausalEdge, CausalNode


class CausalGraph:
    """Mutable graph builder used only during a single diagnostic projection."""

    def __init__(self) -> None:
        self.nodes: dict[str, CausalNode] = {}
        self.out: dict[str, list[CausalEdge]] = {}

    def add_node(self, node: CausalNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: CausalEdge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise KeyError("causal edge references unknown node")
        self.out.setdefault(edge.source, []).append(edge)

    def ensure_node(self, object_id: str, kind: str, **attrs: object) -> None:
        if object_id not in self.nodes:
            self.add_node(CausalNode(object_id, kind, dict(attrs)))

    def ensure_edge(self, source: str, relation: str, target: str) -> None:
        edge = CausalEdge(source, relation, target)
        if edge not in self.out.get(source, ()):
            self.add_edge(edge)


__all__ = ["CausalGraph"]
