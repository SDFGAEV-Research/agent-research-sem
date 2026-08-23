from __future__ import annotations

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import (
    MethodSnapshot,
    MethodTaskCompletionReceipt,
    MethodTaskOutcome,
    RecallRequest,
    RecallResult,
)

from .session_assembly import SEMSessionRuntime
from .session_state_api import SEMSessionClosed
from .session_evolution_api import EvolutionReconciliation
from .task_coordination import SEMEvolutionPostCommitError, SEMEvolutionRecoveryRequired
from .task_lifecycle import SEMTaskLifecycle


class SEMSession:
    """Method ABI façade over an already-composed SEM session runtime."""

    METHOD_ID = "self_evolving_memory"
    task_completion_idempotency = "sem_task_lifecycle.v1"

    @staticmethod
    def task_completion_key(context: ExecutionContext) -> str:
        return SEMTaskLifecycle.key(context)

    def __init__(self, session_id: str, runtime: SEMSessionRuntime) -> None:
        self.session_id = session_id
        self._runtime = runtime

    @property
    def generation(self) -> str:
        return self._runtime.lifecycle.generation

    def ingest(self, evidence: object, context: ExecutionContext) -> None:
        self._runtime.ingest.ingest(evidence, context)

    def recall(self, request: RecallRequest) -> RecallResult:
        return self._runtime.serving.recall(request)

    def task_completed(
        self,
        result: object,
        context: ExecutionContext,
    ) -> MethodTaskCompletionReceipt:
        outcome = result if isinstance(result, MethodTaskOutcome) else None
        return self._runtime.tasks.task_completed(
            self.task_completion_key(context),
            outcome,
            context,
        )

    def reconcile_task(
        self,
        task_key: str,
        context: ExecutionContext,
    ) -> EvolutionReconciliation:
        return self._runtime.tasks.reconcile_task(task_key, context)

    def reconcile_task_completion(
        self,
        completion_key: str,
        context: ExecutionContext,
    ) -> MethodTaskCompletionReceipt | None:
        return self._runtime.tasks.reconcile_task_completion(completion_key, context)

    def checkpoint(self) -> MethodSnapshot:
        return self._runtime.persistence.checkpoint()

    def restore(self, snapshot: MethodSnapshot) -> None:
        self._runtime.persistence.restore(snapshot)

    def flush_observations(self) -> tuple[str, ...]:
        return self._runtime.lifecycle.flush_observations()

    def mutation_history(self, *, limit: int = 64):
        return self._runtime.lifecycle.mutation_history(limit=limit)

    def diagnostics(self) -> dict[str, object]:
        return self._runtime.lifecycle.diagnostics()

    def close(self) -> None:
        self._runtime.lifecycle.close()


__all__ = [
    "SEMSession",
    "SEMSessionClosed",
    "SEMEvolutionPostCommitError",
    "SEMEvolutionRecoveryRequired",
]
