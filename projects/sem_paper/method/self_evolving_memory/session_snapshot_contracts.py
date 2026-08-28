from __future__ import annotations

from dataclasses import dataclass

from research_platform.participant.method.api import MethodObservation

from .evidence_api import EvidenceSnapshot
from .evolution import TelemetrySnapshot
from .session_reducer import SEMSessionState
from .serving import ServingRuntimeState
from .task_lifecycle import TaskProgress


SCHEMA_VERSION = "10"
IMPLEMENTATION_VERSION = "0.31.0"


@dataclass(frozen=True, slots=True)
class SessionMutationRecord:
    revision: int
    mutation_type: str
    before_state_digest: str
    after_state_digest: str
    before_evidence_digest: str
    after_evidence_digest: str
    before_closed: bool
    after_closed: bool
    evidence_sequence: int
    architecture_generation: str
    source_revision: int | None = None
    run_id: str | None = None
    task_id: str | None = None
    decision_cycle_id: str | None = None
    operation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None


@dataclass(frozen=True, slots=True)
class SessionLineageSnapshot:
    revision: int
    mutation_tail: tuple[SessionMutationRecord, ...]


@dataclass(frozen=True, slots=True)
class SEMSessionStateSnapshot:
    """Snapshot owned exclusively by the SEM session-state subsystem."""

    state: SEMSessionState
    evidence: EvidenceSnapshot
    lineage: SessionLineageSnapshot


@dataclass(frozen=True, slots=True)
class SEMSnapshotPayload:
    """Method-level checkpoint payload composed from independent session subsystems."""

    session_state: SEMSessionStateSnapshot
    pending_observations: tuple[MethodObservation, ...]
    task_progress: tuple[TaskProgress, ...]
    evolution_telemetry: TelemetrySnapshot
    serving_state: ServingRuntimeState


__all__ = [
    "IMPLEMENTATION_VERSION",
    "SCHEMA_VERSION",
    "SEMSessionStateSnapshot",
    "SEMSnapshotPayload",
    "SessionLineageSnapshot",
    "SessionMutationRecord",
]
