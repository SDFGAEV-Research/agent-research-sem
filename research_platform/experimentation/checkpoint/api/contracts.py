from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from research_platform.platform.kernel import canonical_digest
from research_platform.participant.core.api.checkpoint import ParticipantCheckpoint, ParticipantCheckpointRef


@dataclass(frozen=True, slots=True)
class RunParticipantSnapshotRef:
    """Run-level metadata around a generic participant checkpoint identity."""

    checkpoint: ParticipantCheckpointRef
    generation: str | None = None

    @property
    def role(self) -> str:
        return self.checkpoint.role


@dataclass(frozen=True, slots=True)
class RunParticipantPayload:
    ref: RunParticipantSnapshotRef
    checkpoint: ParticipantCheckpoint

    def __post_init__(self) -> None:
        if self.ref.checkpoint != self.checkpoint.ref:
            raise ValueError("run participant checkpoint ref does not match checkpoint envelope")


@dataclass(frozen=True, slots=True)
class RunCheckpointManifest:
    checkpoint_id: str
    schema_version: str
    experiment_spec_digest: str
    run_id: str
    session_id: str
    decision_cycle_id: str
    cycle_identity_digest: str
    participant_snapshots: tuple[RunParticipantSnapshotRef, ...]

    def __post_init__(self) -> None:
        required = (
            self.checkpoint_id,
            self.schema_version,
            self.experiment_spec_digest,
            self.run_id,
            self.session_id,
            self.decision_cycle_id,
            self.cycle_identity_digest,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("RunCheckpointManifest identity fields must be non-empty")
        roles = [row.role for row in self.participant_snapshots]
        if len(roles) != len(set(roles)):
            raise ValueError("participant snapshot roles must be unique")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class RunCheckpointBundle:
    manifest: RunCheckpointManifest
    participant_payloads: tuple[RunParticipantPayload, ...]

    def __post_init__(self) -> None:
        manifest_roles = {row.role for row in self.manifest.participant_snapshots}
        payload_roles = tuple(row.ref.role for row in self.participant_payloads)
        if len(payload_roles) != len(set(payload_roles)):
            raise ValueError("run checkpoint bundle participant payload roles must be unique")
        if set(payload_roles) != manifest_roles:
            raise ValueError("run checkpoint bundle payload roles must match the manifest")


class RunCheckpointConflict(RuntimeError):
    pass


class RunCheckpointIntegrityError(RuntimeError):
    pass


@runtime_checkable
class RunCheckpointStore(Protocol):
    durability: str

    def publish(
        self,
        manifest: RunCheckpointManifest,
        participant_payloads: tuple[RunParticipantPayload, ...],
    ) -> RunCheckpointManifest: ...

    def load(self, checkpoint_id: str) -> RunCheckpointBundle: ...


__all__ = [
    "RunCheckpointBundle",
    "RunCheckpointConflict",
    "RunCheckpointIntegrityError",
    "RunCheckpointManifest",
    "RunCheckpointStore",
    "RunParticipantPayload",
    "RunParticipantSnapshotRef",
]
