from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from research_platform.platform.kernel import ExecutionContext, JsonInput


SurfaceT = TypeVar("SurfaceT")
TaskT = TypeVar("TaskT")
ResultT = TypeVar("ResultT")


@runtime_checkable
class ExperimentScientificWorkflow(Protocol[SurfaceT, TaskT, ResultT]):
    workflow_id: str
    configuration_digest: str
    surface_id: str

    def run(
        self,
        surface: SurfaceT,
        context: ExecutionContext,
        *,
        task: TaskT,
        input_kind: str,
        input_payload: JsonInput,
    ) -> ResultT: ...


@dataclass(frozen=True, slots=True)
class ExperimentWorkflowIdentity:
    workflow_id: str
    configuration_digest: str = ""

    def __post_init__(self) -> None:
        if not self.workflow_id.strip():
            raise ValueError("workflow_id must be non-empty")


class ExperimentWorkflowIdentityMismatch(RuntimeError):
    pass


__all__ = [
    "ExperimentScientificWorkflow",
    "ExperimentWorkflowIdentity",
    "ExperimentWorkflowIdentityMismatch",
]
