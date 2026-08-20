from __future__ import annotations

from .retrieval_planner import HybridLexicalRecencyQueryPlanner, LatestEvidenceQueryPlanner
from .serving import MemoryServingService
from .session_serving_api import ServingSessionSource


def build_hybrid_session_serving(source: ServingSessionSource) -> MemoryServingService:
    return MemoryServingService(
        source,
        HybridLexicalRecencyQueryPlanner(max_nodes=8),
    )


def build_latest_evidence_session_serving(source: ServingSessionSource) -> MemoryServingService:
    return MemoryServingService(
        source,
        LatestEvidenceQueryPlanner(),
    )


__all__ = [
    "build_hybrid_session_serving",
    "build_latest_evidence_session_serving",
]
