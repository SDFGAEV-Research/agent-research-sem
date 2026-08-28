from __future__ import annotations

from collections.abc import Sequence

from research_platform.execution.scheduling.api import AdmissionSchedulingPolicyPort, ExecutionPriority, SchedulingCandidate


class FairPrioritySchedulingPolicy(AdmissionSchedulingPolicyPort):
    """Priority aging plus deterministic group fairness; owns ordering only."""

    def __init__(self, *, priority_aging_seconds: float = 1.0) -> None:
        if priority_aging_seconds <= 0:
            raise ValueError("priority aging must be positive")
        self._aging_seconds = float(priority_aging_seconds)
        self._rank = {ExecutionPriority.CRITICAL: 0, ExecutionPriority.HIGH: 1,
                      ExecutionPriority.NORMAL: 2, ExecutionPriority.LOW: 3}

    def _effective_rank(self, candidate: SchedulingCandidate, now: float) -> int:
        waited = max(0.0, now - candidate.enqueued_monotonic)
        return max(0, self._rank[candidate.priority] - int(waited / self._aging_seconds))

    def select(self, candidates: Sequence[SchedulingCandidate], *, group_last_grant: dict[str, int],
               now_monotonic: float) -> int:
        if not candidates:
            raise ValueError("scheduling candidates required")
        ranked = [(self._effective_rank(item, now_monotonic), item) for item in candidates]
        best_rank = min(rank for rank, _ in ranked)
        selected = min((item for rank, item in ranked if rank == best_rank),
                       key=lambda item: (group_last_grant.get(item.group_id, -1), item.ticket))
        return selected.ticket
