from __future__ import annotations

import time
from typing import Callable

from research_platform.observability.status.api import HealthState, SubsystemSnapshot

from .recovery_ports import RecoveryLeaseStatusPort


class RecoveryLeaseStatusProbe:
    def __init__(
        self,
        source: RecoveryLeaseStatusPort,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._source = source
        self._clock = clock

    def snapshot(self) -> SubsystemSnapshot:
        lease = self._source.read()
        if lease is None:
            return SubsystemSnapshot("recovery_lease", HealthState.READY, "no active recovery owner")
        remaining = lease.expires_at - self._clock()
        if remaining <= 0:
            return SubsystemSnapshot(
                "recovery_lease",
                HealthState.FAILED,
                f"expired recovery lease owner={lease.owner_id}",
                evidence=self._source.evidence_refs(),
                next_commands=("inspect stale recovery owner before acquiring a new lease",),
                reason_codes=("recovery_lease_expired",),
            )
        return SubsystemSnapshot(
            "recovery_lease",
            HealthState.READY,
            f"owner={lease.owner_id}; expires_in={remaining:.1f}s",
            evidence=self._source.evidence_refs(),
        )


__all__ = ["RecoveryLeaseStatusProbe"]
