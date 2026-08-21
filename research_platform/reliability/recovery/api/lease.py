from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecoveryLease:
    owner_id: str
    manifest_digest: str
    acquired_at: float
    expires_at: float


class RecoveryLeaseBusy(RuntimeError):
    pass


__all__ = ["RecoveryLease", "RecoveryLeaseBusy"]
