from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Protocol

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

from research_platform.execution.operation.api import OperationId


@dataclass(frozen=True, slots=True)
class WorkflowRunId:
    value: str
    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("workflow_run_id must be text")
        value = self.value.strip()
        if not value:
            raise ValueError("workflow_run_id required")
        object.__setattr__(self, "value", value)


class WorkflowRecoveryDisposition(StrEnum):
    COMPLETED = "completed"
    RETRY_NOT_EXECUTED = "retry_not_executed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class WorkflowReconciliationProof:
    workflow_run_id: WorkflowRunId
    step_id: str
    operation_id: OperationId
    disposition: WorkflowRecoveryDisposition
    evidence_digest: str
    authority: str

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_run_id, WorkflowRunId):
            raise TypeError("workflow reconciliation workflow_run_id must be WorkflowRunId")
        if not isinstance(self.operation_id, OperationId):
            raise TypeError("workflow reconciliation operation_id must be OperationId")
        if not isinstance(self.disposition, WorkflowRecoveryDisposition):
            raise TypeError("workflow reconciliation disposition must be WorkflowRecoveryDisposition")
        if not isinstance(self.step_id, str) or not self.step_id.strip():
            raise ValueError("workflow reconciliation step_id required")
        if not isinstance(self.evidence_digest, str) or not _SHA256.fullmatch(self.evidence_digest):
            raise ValueError("workflow reconciliation evidence_digest must be SHA-256 hex")
        if not isinstance(self.authority, str) or not self.authority.strip():
            raise ValueError("workflow reconciliation authority required")
        object.__setattr__(self, "step_id", self.step_id.strip())
        object.__setattr__(self, "evidence_digest", self.evidence_digest.lower())
        object.__setattr__(self, "authority", self.authority.strip())


@dataclass(frozen=True, slots=True)
class WorkflowOperationBinding:
    step_id: str
    operation_id: OperationId

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str):
            raise TypeError("workflow binding step_id must be text")
        step_id = self.step_id.strip()
        if not step_id:
            raise ValueError("workflow binding step_id required")
        if not isinstance(self.operation_id, OperationId):
            raise TypeError("workflow binding operation_id must be OperationId")
        object.__setattr__(self, "step_id", step_id)


@dataclass(frozen=True, slots=True)
class WorkflowProgress:
    workflow_run_id: WorkflowRunId
    graph_digest: str
    version: int
    completed: tuple[WorkflowOperationBinding, ...] = ()
    running: tuple[WorkflowOperationBinding, ...] = ()
    uncertain: tuple[WorkflowOperationBinding, ...] = ()
    failed: WorkflowOperationBinding | None = None
    cancellation_requested: bool = False
    cancellation_reason: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("workflow progress version must be integer")
        if self.version < 0:
            raise ValueError("workflow progress version cannot be negative")
        if not isinstance(self.graph_digest, str):
            raise TypeError("workflow graph digest must be text")
        digest = self.graph_digest.strip().lower()
        if not _SHA256.fullmatch(digest):
            raise ValueError("workflow graph digest must be SHA-256 hex")
        object.__setattr__(self, "graph_digest", digest)
        groups = (self.completed, self.running, self.uncertain)
        if any(not isinstance(item, WorkflowOperationBinding) for group in groups for item in group):
            raise TypeError("workflow progress bindings must be WorkflowOperationBinding")
        if self.failed is not None and not isinstance(self.failed, WorkflowOperationBinding):
            raise TypeError("workflow failed binding must be WorkflowOperationBinding")
        bindings = tuple(item for group in groups for item in group)
        if self.failed is not None:
            bindings += (self.failed,)
        step_ids = tuple(item.step_id for item in bindings)
        operation_ids = tuple(item.operation_id for item in bindings)
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("workflow step cannot occupy multiple progress states")
        if len(set(operation_ids)) != len(operation_ids):
            raise ValueError("workflow operation identity cannot bind multiple steps")
        if not isinstance(self.cancellation_requested, bool):
            raise TypeError("workflow cancellation_requested must be bool")
        if self.cancellation_reason is not None and not isinstance(self.cancellation_reason, str):
            raise TypeError("workflow cancellation reason must be text or null")
        reason = None if self.cancellation_reason is None else self.cancellation_reason.strip()
        if self.cancellation_requested and not reason:
            raise ValueError("workflow cancellation requires reason")
        if not self.cancellation_requested and reason is not None:
            raise ValueError("workflow cancellation reason requires cancellation_requested")
        object.__setattr__(self, "cancellation_reason", reason)

    @property
    def completed_steps(self) -> tuple[str, ...]:
        return tuple(item.step_id for item in self.completed)

    @property
    def failed_step(self) -> str | None:
        return None if self.failed is None else self.failed.step_id


class WorkflowProgressConflict(RuntimeError): pass
class WorkflowProgressCorruption(RuntimeError): pass


class WorkflowProgressStorePort(Protocol):
    @property
    def durability(self) -> str: ...
    def create(self, progress: WorkflowProgress) -> WorkflowProgress: ...
    def load(self, workflow_run_id: WorkflowRunId) -> WorkflowProgress | None: ...
    def compare_and_swap(self, expected_version: int, progress: WorkflowProgress) -> WorkflowProgress: ...


__all__ = ["WorkflowOperationBinding", "WorkflowProgress", "WorkflowProgressConflict",
           "WorkflowProgressCorruption", "WorkflowProgressStorePort", "WorkflowReconciliationProof", "WorkflowRecoveryDisposition", "WorkflowRunId"]
