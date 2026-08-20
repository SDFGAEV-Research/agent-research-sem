from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from research_platform.platform.kernel.context import ExecutionContext


@dataclass(frozen=True, slots=True)
class MethodIdentity:
    method_id: str
    implementation_version: str
    abi_version: str
    schema_version: str
    artifact_digest: str = ""


@dataclass(frozen=True, slots=True)
class MethodSnapshot:
    method_id: str
    implementation_version: str
    schema_version: str
    method_runtime_binding_digest: str
    session_id: str
    payload_sha256: str
    opaque_payload: bytes


@dataclass(frozen=True, slots=True)
class RecallRequest:
    intent: str
    context: ExecutionContext
    limit: int = 8


@dataclass(frozen=True, slots=True)
class RecallResult:
    context_text: str
    method_generation: str
    artifacts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MethodTaskCompletionReceipt:
    completion_key: str
    method_generation: str | None = None
    artifacts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.completion_key.strip():
            raise ValueError("completion_key must be non-empty")


@runtime_checkable
class IdempotentTaskCompletionSession(Protocol):
    """Optional capability required by crash-durable cross-component recovery."""

    task_completion_idempotency: str
    def task_completion_key(self, context: ExecutionContext) -> str: ...


@runtime_checkable
class TaskCompletionReconciliationSession(Protocol):
    """Optional stronger capability for COMMIT_ONLY crash recovery.

    The implementation may reconcile local session state from its own authoritative
    method state, but it must never execute a new task completion.  ``None`` means
    the method cannot prove that the completion key was committed.
    """

    def reconcile_task_completion(
        self, completion_key: str, context: ExecutionContext
    ) -> MethodTaskCompletionReceipt | None: ...


@runtime_checkable
class MethodSession(Protocol):
    def recall(self, request: RecallRequest) -> RecallResult: ...
    def ingest(self, evidence: object, context: ExecutionContext) -> None: ...
    def task_completed(self, result: object, context: ExecutionContext) -> MethodTaskCompletionReceipt | None: ...
    def checkpoint(self) -> MethodSnapshot: ...
    def restore(self, snapshot: MethodSnapshot) -> None: ...
    def diagnostics(self) -> dict[str, object]: ...
    def close(self) -> None: ...
