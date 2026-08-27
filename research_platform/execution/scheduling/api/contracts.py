from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExecutionPriority(StrEnum):
    """Generic scheduling intent; ranking semantics belong to scheduling runtime."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class SchedulingCandidate:
    ticket: int
    group_id: str
    priority: ExecutionPriority
    enqueued_monotonic: float
