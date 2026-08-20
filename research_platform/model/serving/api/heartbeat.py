from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True, slots=True)
class ServiceHeartbeat:
    deployment_id: str
    stack_digest: str
    pid: int
    process_start_marker: str
    argv_digest: str
    ready: bool
    qualification_digest: str | None
    timestamp: float

    def age(self, now: float | None = None) -> float:
        return max(0.0, (time.time() if now is None else now) - self.timestamp)
