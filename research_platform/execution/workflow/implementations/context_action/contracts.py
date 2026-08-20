from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from research_platform.environment.runtime.api import ActionResult, Observation
from research_platform.platform.kernel import ExecutionContext, OperationResult
from research_platform.participant.method.api import MethodTaskCompletionReceipt, RecallResult


@dataclass(frozen=True, slots=True)
class StudyTaskCompletionExecution:
    receipt: MethodTaskCompletionReceipt | None
    operation_results: tuple[OperationResult[object], ...]


@runtime_checkable
class ContextActionOperationPort(Protocol):
    def preflight_action(self, action_type: str, action_payload: object, context: ExecutionContext) -> tuple[OperationResult[object], ...]: ...
    def try_recover_committed_cycle(self, action_type: str, action_payload: object, context: ExecutionContext) -> object | None: ...
    def observe(self, context: ExecutionContext) -> tuple[Observation, OperationResult[object]]: ...
    def ingest(self, observation: Observation, context: ExecutionContext) -> OperationResult[object]: ...
    def recall(self, task_text: str, context: ExecutionContext) -> tuple[RecallResult, OperationResult[object]]: ...
    def act(self, action_type: str, action_payload: object, context: ExecutionContext) -> tuple[ActionResult, tuple[OperationResult[object], ...]]: ...
    def task_completed(self, action_result: ActionResult, context: ExecutionContext) -> StudyTaskCompletionExecution: ...


__all__ = ["ContextActionOperationPort", "StudyTaskCompletionExecution"]
