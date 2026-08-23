from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from research_platform.experimentation.workload import WorkloadBatchBindingPort

from research_platform.experimentation.workload.api import WorkloadBatchResult

from research_platform.platform.kernel import ExecutionContext

from .workload import (
    WorkloadCheckpointBindingPort,
    WorkloadCheckpointBundle,
    WorkloadCheckpointManifest,
    WorkloadCheckpointStore,
    WorkloadExecutionCut,
)


class WorkloadCheckpointPublicationPort(Protocol):
    """Durably publish the latest committed checkpoint identity for recovery."""

    def published(self, manifest: WorkloadCheckpointManifest) -> None: ...


@dataclass(frozen=True, slots=True)
class CheckpointedWorkloadBatchResult:
    """Typed batch outcome shared by checkpoint executors and project adapters."""

    batch: WorkloadBatchResult
    latest_checkpoint_id: str | None
    resumed_from_checkpoint_id: str | None = None


class WorkloadCheckpointCoordinatorPort(Protocol):
    def capture(
        self,
        *,
        binding: WorkloadCheckpointBindingPort,
        context: ExecutionContext,
        execution_cut: WorkloadExecutionCut,
    ) -> WorkloadCheckpointManifest: ...

    def restore(
        self,
        checkpoint_id: str,
        *,
        binding: WorkloadCheckpointBindingPort,
        context: ExecutionContext,
    ) -> WorkloadCheckpointBundle: ...


class WorkloadCheckpointedBatchExecutorPort(Protocol):
    """Project-facing seam for checkpoint-aware workload execution."""

    def execute(
        self,
        batch_binding: "WorkloadBatchBindingPort",
        *,
        checkpoint_binding: WorkloadCheckpointBindingPort,
        resume_checkpoint_id: str | None = None,
    ) -> CheckpointedWorkloadBatchResult: ...


__all__ = [
    "CheckpointedWorkloadBatchResult",
    "WorkloadCheckpointCoordinatorPort",
    "WorkloadCheckpointPublicationPort",
    "WorkloadCheckpointedBatchExecutorPort",
]
