from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from research_platform.platform.kernel import ExecutionContext


class TaskPhase(StrEnum):
    OBSERVATION_PENDING = "observation_pending"
    EVOLUTION_PENDING = "evolution_pending"
    EVOLUTION_UNCERTAIN = "evolution_uncertain"
    ADOPTION_OBSERVATION_PENDING = "adoption_observation_pending"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class TaskProgress:
    task_key: str
    phase: TaskPhase
    base_generation: str
    final_generation: str | None = None
    terminal_reason: str | None = None


class TaskLifecycleConflict(RuntimeError):
    pass


class SEMTaskLifecycle:
    """Owns task idempotency/recovery phases; it has no scientific-state authority."""

    def __init__(self) -> None:
        self._rows: dict[str, TaskProgress] = {}

    @staticmethod
    def key(context: ExecutionContext) -> str:
        # Scientific idempotency must survive tracing/span/operation-wrapper changes.
        # A decision cycle is the strongest stable completion identity in Study runs.
        if context.decision_cycle_id:
            return f"decision_cycle:{context.run_id}:{context.decision_cycle_id}"
        if context.task_id:
            return f"task:{context.run_id}:{context.task_id}"
        if context.operation_id:
            return f"operation:{context.operation_id}"
        return f"span:{context.run_id}:{context.trace_id}:{context.span_id}"

    def get(self, task_key: str) -> TaskProgress | None:
        return self._rows.get(task_key)

    def begin(self, task_key: str, *, base_generation: str) -> TaskProgress:
        if task_key in self._rows:
            raise TaskLifecycleConflict(f"SEM task already exists: {task_key}")
        row = TaskProgress(task_key, TaskPhase.OBSERVATION_PENDING, base_generation)
        self._rows[task_key] = row
        return row

    def transition(
        self,
        task_key: str,
        *,
        expected: TaskPhase,
        target: TaskPhase,
        final_generation: str | None = None,
    ) -> TaskProgress:
        current = self._rows.get(task_key)
        if current is None:
            raise TaskLifecycleConflict(f"SEM task does not exist: {task_key}")
        if current.phase is not expected:
            raise TaskLifecycleConflict(
                f"SEM task phase conflict for {task_key}: expected={expected.value} actual={current.phase.value}"
            )
        if target is TaskPhase.ADOPTION_OBSERVATION_PENDING and not final_generation:
            raise TaskLifecycleConflict("adoption observation phase requires final generation")
        row = TaskProgress(
            task_key,
            target,
            current.base_generation,
            final_generation if final_generation is not None else current.final_generation,
            current.terminal_reason,
        )
        self._rows[task_key] = row
        return row

    def complete_after_failed_evolution(self, task_key: str, *, reason: str) -> TaskProgress:
        current = self._rows.get(task_key)
        if current is None or current.phase is not TaskPhase.EVOLUTION_UNCERTAIN:
            actual = current.phase.value if current is not None else "missing"
            raise TaskLifecycleConflict(
                f"SEM task cannot reconcile failed evolution from phase: {actual}"
            )
        row = TaskProgress(
            task_key, TaskPhase.COMPLETED, current.base_generation,
            current.final_generation, reason,
        )
        self._rows[task_key] = row
        return row

    def snapshot(self) -> tuple[TaskProgress, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def restore(self, rows: Iterable[TaskProgress]) -> None:
        restored: dict[str, TaskProgress] = {}
        for row in rows:
            if row.task_key in restored:
                raise ValueError("SEM task lifecycle snapshot contains duplicate task keys")
            restored[row.task_key] = row
        self._rows = restored

    def phase_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self._rows.values():
            counts[row.phase.value] = counts.get(row.phase.value, 0) + 1
        return dict(sorted(counts.items()))

    def terminal_reason_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self._rows.values():
            if row.terminal_reason:
                counts[row.terminal_reason] = counts.get(row.terminal_reason, 0) + 1
        return dict(sorted(counts.items()))


__all__ = [
    "SEMTaskLifecycle",
    "TaskLifecycleConflict",
    "TaskPhase",
    "TaskProgress",
]
