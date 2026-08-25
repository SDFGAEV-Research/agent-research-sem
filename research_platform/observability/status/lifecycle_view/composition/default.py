from __future__ import annotations

from research_platform.platform.kernel.leaf_contract import LeafHandler
from research_platform.observability.status.lifecycle_view.providers.default import bind as bind_provider

def compose(handler: LeafHandler, state_path=None):
    """Compose one executable leaf runtime with explicit domain behavior."""
    return bind_provider(handler, state_path)

__all__ = ["compose"]
