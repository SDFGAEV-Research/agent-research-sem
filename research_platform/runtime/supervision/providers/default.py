from __future__ import annotations

from research_platform.platform.kernel.leaf_contract import LeafHandler, SystemLeafProvider
from research_platform.runtime.supervision.api.boundary import CONTRACT

PROVIDER = SystemLeafProvider(CONTRACT)

def provider() -> SystemLeafProvider:
    return PROVIDER

def bind(handler: LeafHandler, state_path=None):
    return PROVIDER.bind(handler, state_path)

__all__ = ["PROVIDER", "provider", "bind"]
