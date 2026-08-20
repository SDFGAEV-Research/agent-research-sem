from __future__ import annotations

import json
from pathlib import Path

from research_platform.model.deployment.api import (
    ModelControllerPhase,
    ModelControllerState,
    ModelDeploymentStatus,
    ModelDesiredState,
    ModelReconcileCycle,
    ModelRuntimeState,
)
from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes


class FileModelControllerStateStore:
    """Small durable operational read model for the long-running reconcile controller."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> ModelControllerState | None:
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text("utf-8"))
        cycle_data = data.get("last_cycle")
        cycle = None if cycle_data is None else ModelReconcileCycle(
            cycle_index=int(cycle_data["cycle_index"]),
            completed_at_utc=str(cycle_data["completed_at_utc"]),
            statuses=tuple(self._status_from_data(item) for item in cycle_data.get("statuses", ())),
        )
        return ModelControllerState(
            controller_id=str(data["controller_id"]),
            phase=ModelControllerPhase(str(data["phase"])),
            pid=(int(data["pid"]) if data.get("pid") is not None else None),
            started_at_utc=str(data["started_at_utc"]),
            heartbeat_at_utc=str(data["heartbeat_at_utc"]),
            interval_seconds=float(data["interval_seconds"]),
            cycle_count=int(data["cycle_count"]),
            last_cycle=cycle,
            detail=str(data.get("detail", "")),
        )

    def write(self, state: ModelControllerState) -> ModelControllerState:
        atomic_replace_bytes(self._path, self._encode(state))
        return state

    @staticmethod
    def _status_from_data(data: dict[str, object]) -> ModelDeploymentStatus:
        return ModelDeploymentStatus(
            deployment_id=str(data["deployment_id"]),
            service_id=str(data["service_id"]),
            desired_state=ModelDesiredState(str(data["desired_state"])),
            runtime_state=ModelRuntimeState(str(data["runtime_state"])),
            pid=(int(data["pid"]) if data.get("pid") is not None else None),
            detail=str(data.get("detail", "")),
        )

    @staticmethod
    def _encode(state: ModelControllerState) -> bytes:
        cycle = state.last_cycle
        payload = {
            "controller_id": state.controller_id,
            "phase": state.phase.value,
            "pid": state.pid,
            "started_at_utc": state.started_at_utc,
            "heartbeat_at_utc": state.heartbeat_at_utc,
            "interval_seconds": state.interval_seconds,
            "cycle_count": state.cycle_count,
            "detail": state.detail,
            "last_cycle": None if cycle is None else {
                "cycle_index": cycle.cycle_index,
                "completed_at_utc": cycle.completed_at_utc,
                "statuses": [
                    {
                        "deployment_id": status.deployment_id,
                        "service_id": status.service_id,
                        "desired_state": status.desired_state.value,
                        "runtime_state": status.runtime_state.value,
                        "pid": status.pid,
                        "detail": status.detail,
                    }
                    for status in cycle.statuses
                ],
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


__all__ = ["FileModelControllerStateStore"]
