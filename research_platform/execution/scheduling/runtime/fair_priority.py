from __future__ import annotations

from collections.abc import Sequence

from research_platform.execution.scheduling.api import (
    AdmissionSchedulingPolicyPort,
    ExecutionPriority,
    SchedulingCandidate,
)


class FairPrioritySchedulingPolicy(AdmissionSchedulingPolicyPort):
    """Priority aging plus group-round-robin fairness for admission waiters.

    This system owns only ordering. It receives already-admissible candidates and
    never reads live resource state or mutates capacity/accounting.
    """

    def __init__(self, *, priority_aging_seconds: float = 1.0) -> None:
        if priority_aging_seconds <= 0:
            raise ValueError("priority aging must be positive")
        self._aging_seconds = float(priority_aging_seconds)
        self._rank = {
            ExecutionPriority.CRITICAL: 0,
            ExecutionPriority.HIGH: 1,
            ExecutionPriority.NORMAL: 2,
            ExecutionPriority.LOW: 3,
        }

    def _effective_rank(self, candidate: SchedulingCandidate, now: float) -> int:
        waited = max(0.0, now - candidate.enqueued_monotonic)
        promotions = int(waited / self._aging_seconds)
        return max(0, self._rank[candidate.priority] - promotions)

    def select(
        self,
        candidates: Sequence[SchedulingCandidate],
        *,
        group_last_grant: dict[str, int],
        now_monotonic: float,
    ) -> int:
        if not candidates:
            raise ValueError("scheduling candidates required")
        best_rank = min(self._effective_rank(item, now_monotonic) for item in candidates)
        prioritized = [
            item for item in candidates
            if self._effective_rank(item, now_monotonic) == best_rank
        ]
        selected = min(
            prioritized,
            key=lambda item: (group_last_grant.get(item.group_id, -1), item.ticket),
        )
        return selected.ticket
