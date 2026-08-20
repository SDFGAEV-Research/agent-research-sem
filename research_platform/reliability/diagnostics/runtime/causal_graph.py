from __future__ import annotations

from research_platform.reliability.diagnostics.api import DiagnosticEvidencePort, DiagnosticIndexSessionPort

from .causal_contracts import CausalGraphSnapshot
from .causal_model import CausalGraph
from .causal_projection import ContextProjector, PayloadProjector, ReferenceProjector


class CausalGraphService:
    """Build an immutable causal graph snapshot from backend-independent diagnostic evidence."""

    def __init__(
        self,
        evidence: DiagnosticEvidencePort,
        projectors: tuple[PayloadProjector, ...] | None = None,
    ) -> None:
        self.evidence = evidence
        self.projectors = projectors or (ContextProjector(), ReferenceProjector())

    def _project_object(self, graph: CausalGraph, payload: dict[str, object]) -> str | None:
        object_id = payload.get("failure_id") or payload.get("event_id") or payload.get("mutation_id")
        if not object_id:
            return None
        object_id = str(object_id)
        kind = "failure" if payload.get("failure_id") else "mutation" if payload.get("mutation_id") else "event"
        attrs = {
            key: payload.get(key)
            for key in ("failure_domain", "failure_code", "stage", "event_type", "state_name", "created_at", "timestamp")
            if payload.get(key) is not None
        }
        graph.ensure_node(object_id, kind, **attrs)
        for projector in self.projectors:
            projector.project(graph, object_id, payload)
        return object_id

    def build(
        self,
        root_id: str,
        *,
        related_limit: int = 200,
        index: DiagnosticIndexSessionPort | None = None,
    ) -> CausalGraphSnapshot:
        idx = index or self.evidence
        root = idx.locate(root_id)
        if root is None:
            raise KeyError(f"object not found: {root_id}")
        graph = CausalGraph()
        self._project_object(graph, root)
        for payload in idx.related_to(root_id, limit=related_limit):
            self._project_object(graph, payload)
        nodes = tuple(
            {"node_id": node.node_id, "kind": node.kind, "attrs": dict(node.attrs)}
            for node in sorted(graph.nodes.values(), key=lambda item: (item.kind, item.node_id))
        )
        edges = tuple(
            {"source": edge.source, "relation": edge.relation, "target": edge.target}
            for source in sorted(graph.out)
            for edge in sorted(graph.out[source], key=lambda item: (item.relation, item.target))
        )
        return CausalGraphSnapshot(root_id=root_id, nodes=nodes, edges=edges)


__all__ = ["CausalGraphService"]
