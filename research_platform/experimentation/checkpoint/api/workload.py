from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
from typing import Protocol, runtime_checkable

from research_platform.platform.kernel import canonical_digest


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class WorkloadRestoreStateCertainty(StrEnum):
    UNCHANGED = "UNCHANGED"
    ROLLED_BACK = "ROLLED_BACK"
    UNKNOWN = "UNKNOWN"


class WorkloadCheckpointRestoreError(RuntimeError):
    """Restore failed with explicit post-failure state certainty."""

    def __init__(
        self,
        *,
        phase: str,
        component_id: str,
        primary: BaseException,
        state_certainty: WorkloadRestoreStateCertainty,
        rollback_errors: tuple[tuple[str, BaseException], ...] = (),
    ) -> None:
        message = (
            "workload checkpoint restore failed: "
            f"phase={phase} component={component_id} state={state_certainty.value}"
        )
        if rollback_errors:
            message += f" rollback_failures={len(rollback_errors)}"
        super().__init__(message)
        self.phase = phase
        self.component_id = component_id
        self.primary = primary
        self.state_certainty = state_certainty
        self.rollback_errors = rollback_errors


@dataclass(frozen=True, slots=True)
class WorkloadExecutionCut:
    """A resumable task-boundary cut shared by every workload adapter.

    A cut is deliberately a task boundary, not an inferred position from a
    result file.  The task ids, optional current task and status are persisted
    with the component snapshots so recovery cannot silently mix a method
    snapshot from one execution prefix with an environment snapshot from
    another prefix.
    """

    completed_task_ids: tuple[str, ...]
    current_task_id: str | None = None
    decision_cycle_id: str | None = None
    status: str = "after_task"

    def __post_init__(self) -> None:
        if any(not item.strip() for item in self.completed_task_ids):
            raise ValueError("workload execution cut task ids must be non-empty")
        if len(set(self.completed_task_ids)) != len(self.completed_task_ids):
            raise ValueError("workload execution cut task ids must be unique")
        if self.current_task_id is not None and not self.current_task_id.strip():
            raise ValueError("current workload task id cannot be empty")
        if self.current_task_id in self.completed_task_ids:
            raise ValueError("current workload task cannot already be completed")
        if self.status not in {"after_task", "in_task", "closed"}:
            raise ValueError(f"unsupported workload execution cut status: {self.status}")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class WorkloadCheckpointComponentRef:
    component_id: str
    codec_id: str
    schema_version: str
    payload_sha256: str
    payload_size: int

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (self.component_id, self.codec_id, self.schema_version, self.payload_sha256)
        ):
            raise ValueError("workload checkpoint component identity is incomplete")
        if len(self.payload_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.payload_sha256
        ):
            raise ValueError("workload checkpoint component payload hash must be SHA-256")
        if self.payload_size < 0:
            raise ValueError("workload checkpoint component payload size cannot be negative")


@dataclass(frozen=True, slots=True)
class WorkloadCheckpointPayload:
    ref: WorkloadCheckpointComponentRef
    payload: bytes

    def __post_init__(self) -> None:
        if _sha256(self.payload) != self.ref.payload_sha256:
            raise ValueError(f"workload checkpoint payload digest mismatch: {self.ref.component_id}")
        if len(self.payload) != self.ref.payload_size:
            raise ValueError(f"workload checkpoint payload size mismatch: {self.ref.component_id}")


@dataclass(frozen=True, slots=True)
class WorkloadCheckpointManifest:
    checkpoint_id: str
    schema_version: str
    run_id: str
    study_id: str
    workload_id: str
    branch_id: str
    source_cut_id: str
    environment_generation: str
    method_generation: str
    task_manifest_digest: str
    execution_cut: WorkloadExecutionCut
    execution_cut_digest: str
    component_refs: tuple[WorkloadCheckpointComponentRef, ...]

    def __post_init__(self) -> None:
        required = (
            self.checkpoint_id,
            self.schema_version,
            self.run_id,
            self.study_id,
            self.workload_id,
            self.branch_id,
            self.source_cut_id,
            self.environment_generation,
            self.method_generation,
            self.task_manifest_digest,
            self.execution_cut_digest,
        )
        if any(not value.strip() for value in required):
            raise ValueError("workload checkpoint manifest identity is incomplete")
        if self.execution_cut.digest() != self.execution_cut_digest:
            raise ValueError("workload checkpoint execution cut digest mismatch")
        ids = [item.component_id for item in self.component_refs]
        if len(ids) != len(set(ids)):
            raise ValueError("workload checkpoint component ids must be unique")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class WorkloadCheckpointBundle:
    manifest: WorkloadCheckpointManifest
    payloads: tuple[WorkloadCheckpointPayload, ...]

    def __post_init__(self) -> None:
        expected = {item.component_id for item in self.manifest.component_refs}
        actual = {item.ref.component_id for item in self.payloads}
        if expected != actual:
            raise ValueError("workload checkpoint payload topology does not match manifest")


@runtime_checkable
class WorkloadCheckpointStore(Protocol):
    durability: str

    def publish(
        self,
        manifest: WorkloadCheckpointManifest,
        payloads: tuple[WorkloadCheckpointPayload, ...],
    ) -> WorkloadCheckpointManifest: ...

    def load(self, checkpoint_id: str) -> WorkloadCheckpointBundle: ...


@runtime_checkable
class WorkloadCheckpointComponentPort(Protocol):
    component_id: str
    codec_id: str
    schema_version: str

    def capture(self) -> bytes: ...

    def restore(self, payload: bytes) -> None: ...


@runtime_checkable
class WorkloadCheckpointBindingPort(Protocol):
    run_id: str
    study_id: str
    workload_id: str
    branch_id: str
    source_cut_id: str
    environment_generation: str
    method_generation: str
    task_manifest_digest: str

    def checkpoint_components(self) -> tuple[WorkloadCheckpointComponentPort, ...]: ...


def build_workload_checkpoint_manifest(
    *,
    run_id: str,
    study_id: str,
    workload_id: str,
    branch_id: str,
    source_cut_id: str,
    environment_generation: str,
    method_generation: str,
    task_manifest_digest: str,
    execution_cut: WorkloadExecutionCut,
    component_refs: tuple[WorkloadCheckpointComponentRef, ...],
    schema_version: str = "1",
) -> WorkloadCheckpointManifest:
    identity = {
        "schema_version": schema_version,
        "run_id": run_id,
        "study_id": study_id,
        "workload_id": workload_id,
        "branch_id": branch_id,
        "source_cut_id": source_cut_id,
        "environment_generation": environment_generation,
        "method_generation": method_generation,
        "task_manifest_digest": task_manifest_digest,
        "execution_cut": execution_cut,
        "component_refs": component_refs,
    }
    return WorkloadCheckpointManifest(
        checkpoint_id=f"workload-checkpoint:{canonical_digest(identity)}",
        schema_version=schema_version,
        run_id=run_id,
        study_id=study_id,
        workload_id=workload_id,
        branch_id=branch_id,
        source_cut_id=source_cut_id,
        environment_generation=environment_generation,
        method_generation=method_generation,
        task_manifest_digest=task_manifest_digest,
        execution_cut=execution_cut,
        execution_cut_digest=execution_cut.digest(),
        component_refs=component_refs,
    )


__all__ = [
    "WorkloadCheckpointBindingPort",
    "WorkloadCheckpointRestoreError",
    "WorkloadCheckpointBundle",
    "WorkloadCheckpointComponentPort",
    "WorkloadCheckpointComponentRef",
    "WorkloadCheckpointManifest",
    "WorkloadCheckpointPayload",
    "WorkloadCheckpointStore",
    "WorkloadExecutionCut",
    "WorkloadRestoreStateCertainty",
    "build_workload_checkpoint_manifest",
]
