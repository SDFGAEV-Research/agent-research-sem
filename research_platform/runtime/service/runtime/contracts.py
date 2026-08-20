from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from research_platform.runtime.service.api import ServiceProcessIdentity


class ServiceExitClass(IntEnum):
    CLEAN = 0
    SOFTWARE = 70
    IO_ERROR = 74
    TEMPORARY = 75
    CONFIGURATION = 78


class ServicePhase(StrEnum):
    NEW = "new"
    VERIFY_CONTRACT = "verify_contract"
    RECONCILE_PRIOR = "reconcile_prior"
    START_CHILD = "start_child"
    WAIT_READY = "wait_ready"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPING = "stopping"
    EXITED = "exited"
    FAILED = "failed"
    RECOVERY_REQUIRED = "recovery_required"


@dataclass(frozen=True, slots=True)
class ServiceReadyEvidence:
    contract_digest: str
    process: ServiceProcessIdentity
    readiness_ref: str
    stdout_capture_ref: str
    stderr_capture_ref: str
    ready_at: float


__all__ = ["ServiceExitClass", "ServicePhase", "ServiceReadyEvidence"]
