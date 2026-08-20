from __future__ import annotations

import json
from pathlib import Path

from research_platform.observability.status.api import HealthState, SubsystemSnapshot


class JsonStateStatusProbe:
    """Generic read-only projection for simple external JSON phase records."""

    def __init__(self, subsystem: str, path: Path) -> None:
        self._subsystem = subsystem
        self._path = path

    def snapshot(self) -> SubsystemSnapshot:
        if not self._path.exists():
            return SubsystemSnapshot(
                self._subsystem,
                HealthState.UNKNOWN,
                f"state record missing: {self._path}",
                reason_codes=("state_record_missing",),
            )
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        phase = str(payload.get("phase", payload.get("state", "unknown")))
        failure_id = payload.get("last_failure_id")
        state = HealthState.FAILED if phase in {"failed", "recovery_required"} else HealthState.READY
        return SubsystemSnapshot(
            subsystem=self._subsystem,
            state=state,
            summary=f"phase={phase}",
            evidence=(str(self._path),),
            failure_id=str(failure_id) if failure_id else None,
            reason_codes=((f"state_phase_{phase}",) if state is HealthState.FAILED else ()),
        )


__all__ = ["JsonStateStatusProbe"]
