from __future__ import annotations

from research_platform.platform.kernel.leaf_contract import LeafHandler
from research_platform.execution.scheduling.providers.default import bind as bind_provider
from research_platform.execution.scheduling.runtime import FairPrioritySchedulingPolicy


def compose(handler: LeafHandler, state_path=None):
    """Compose the standard executable leaf boundary for execution/scheduling."""
    return bind_provider(handler, state_path)


def build_admission_scheduling_policy(*, priority_aging_seconds: float = 1.0) -> FairPrioritySchedulingPolicy:
    """Compose the scheduling policy used by execution/admission."""
    return FairPrioritySchedulingPolicy(priority_aging_seconds=priority_aging_seconds)


__all__ = ["compose", "build_admission_scheduling_policy"]
