from __future__ import annotations

"""Executable runtime owner for observability/tracing/storage."""

from research_platform.platform.kernel.leaf_contract import (
    BoundSystemLeafRuntime, LeafHandler, SystemLeafRuntimeOwner,
)
from research_platform.observability.tracing.storage.api.boundary import CONTRACT

OWNER = SystemLeafRuntimeOwner(CONTRACT)

def owner() -> SystemLeafRuntimeOwner:
    return OWNER

def runtime(handler: LeafHandler, state_path=None) -> BoundSystemLeafRuntime:
    """Bind domain behavior; no handler means no execution is permitted."""
    return OWNER.bind(handler, state_path)

__all__ = ["OWNER", "owner", "runtime"]
