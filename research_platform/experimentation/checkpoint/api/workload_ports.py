from __future__ import annotations

from typing import Protocol

from research_platform.platform.kernel import ExecutionContext

from .workload import (
    WorkloadCheckpointBindingPort,
    WorkloadCheckpointBundle,
    WorkloadCheckpointManifest,
    WorkloadCheckpointStore,
    WorkloadExecutionCut,
)


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


__all__ = ["WorkloadCheckpointCoordinatorPort"]
