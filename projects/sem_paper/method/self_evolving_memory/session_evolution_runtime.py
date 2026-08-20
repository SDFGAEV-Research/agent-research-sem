from __future__ import annotations

from research_platform.platform.kernel import ExecutionContext

from .evolution import EvolutionOutcome, EvolutionPipeline
from .session_state_api import SEMSessionStatePort
from .session_evolution_api import (
    EvolutionReconciliation,
    EvolutionReconciliationPort,
    EvolutionReconciliationStatus,
    EvolutionSessionSnapshot,
    EvolutionSessionSource,
    SessionEvolutionController,
)


class ConservativeEvolutionReconciler:
    def reconcile(
        self,
        *,
        task_key: str,
        base_generation: str,
        context: ExecutionContext,
    ) -> EvolutionReconciliation:
        del task_key, base_generation, context
        return EvolutionReconciliation(
            EvolutionReconciliationStatus.UNRESOLVED,
            reason="no authoritative evolution reconciliation port configured",
        )


class ReadOnlyEvolutionSessionSource:
    """Runtime adapter exposing only the evolution read model, never the session cell."""

    def __init__(self, cell: SEMSessionStatePort) -> None:
        self._cell = cell

    def snapshot(self) -> EvolutionSessionSnapshot:
        generation, evidence_sequence, evidence_digest, tasks_completed, evolution_epoch = (
            self._cell.evolution_summary()
        )
        return EvolutionSessionSnapshot(
            generation=generation,
            evidence_sequence=evidence_sequence,
            evidence_digest=evidence_digest,
            tasks_completed=tasks_completed,
            evolution_epoch=evolution_epoch,
        )


class DisabledSessionEvolution:
    """Explicit no-evolution provider; absence of evolution never triggers hidden behavior."""

    def on_task_completed(self, context: ExecutionContext) -> EvolutionOutcome | None:
        del context
        return None

    def reconcile_uncertain(
        self,
        *,
        task_key: str,
        base_generation: str,
        context: ExecutionContext,
    ) -> EvolutionReconciliation:
        del task_key, context
        return EvolutionReconciliation(
            EvolutionReconciliationStatus.NO_AUTHORITATIVE_ADOPTION,
            authoritative_generation=base_generation,
            reason="evolution is disabled",
        )


class DisabledSessionEvolutionFactory:
    def __call__(self, source: EvolutionSessionSource) -> SessionEvolutionController:
        del source
        return DisabledSessionEvolution()


class PipelineSessionEvolution:
    """Runtime adapter only; scientific and reconciliation authority stay in injected ports."""

    def __init__(
        self,
        pipeline: EvolutionPipeline,
        reconciliation: EvolutionReconciliationPort | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._reconciliation = reconciliation or ConservativeEvolutionReconciler()

    def on_task_completed(self, context: ExecutionContext) -> EvolutionOutcome:
        del context
        return self._pipeline.run()

    def reconcile_uncertain(
        self,
        *,
        task_key: str,
        base_generation: str,
        context: ExecutionContext,
    ) -> EvolutionReconciliation:
        return self._reconciliation.reconcile(
            task_key=task_key,
            base_generation=base_generation,
            context=context,
        )


__all__ = [
    "ConservativeEvolutionReconciler",
    "DisabledSessionEvolution",
    "DisabledSessionEvolutionFactory",
    "PipelineSessionEvolution",
    "ReadOnlyEvolutionSessionSource",
]
