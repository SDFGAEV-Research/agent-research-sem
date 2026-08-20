from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from research_platform.platform.kernel import ExecutionContext


@runtime_checkable
class ExperimentScientificWorkflow(Protocol):
    workflow_id: str
    configuration_digest: str
    surface_id: str

    def run(
        self,
        surface: object,
        context: ExecutionContext,
        *,
        task: object,
        input_kind: str,
        input_payload: object,
    ) -> object: ...


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
