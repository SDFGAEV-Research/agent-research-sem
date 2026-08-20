from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from research_platform.platform.kernel import ExecutionContext

from .evolution import EvolutionOutcome


class EvolutionReconciliationStatus(StrEnum):
    NO_AUTHORITATIVE_ADOPTION = "no_authoritative_adoption"
    ADOPTION_CONFIRMED = "adoption_confirmed"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class EvolutionReconciliation:
    status: EvolutionReconciliationStatus
    authoritative_generation: str | None = None
    evidence_refs: tuple[str, ...] = ()
    reason: str | None = None


class EvolutionReconciliationPort(Protocol):
    def reconcile(
        self,
        *,
        task_key: str,
        base_generation: str,
        context: ExecutionContext,
    ) -> EvolutionReconciliation: ...


@dataclass(frozen=True, slots=True)
class EvolutionSessionSnapshot:
    generation: str
    evidence_sequence: int
    evidence_digest: str
    tasks_completed: int
    evolution_epoch: int


class EvolutionSessionSource(Protocol):
    def snapshot(self) -> EvolutionSessionSnapshot: ...


class SessionEvolutionController(Protocol):
    def on_task_completed(self, context: ExecutionContext) -> EvolutionOutcome | None: ...

    def reconcile_uncertain(
        self,
        *,
        task_key: str,
        base_generation: str,
        context: ExecutionContext,
    ) -> EvolutionReconciliation: ...


class SessionEvolutionFactory(Protocol):
    def __call__(self, source: EvolutionSessionSource) -> SessionEvolutionController: ...


__all__ = [
    "EvolutionReconciliation",
    "EvolutionReconciliationPort",
    "EvolutionReconciliationStatus",
    "EvolutionSessionSnapshot",
    "EvolutionSessionSource",
    "SessionEvolutionController",
    "SessionEvolutionFactory",
]
