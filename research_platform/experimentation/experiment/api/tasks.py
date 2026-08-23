from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class ExperimentTaskSpec:
    """Environment-neutral task graph node used by every experiment backend."""

    task_id: str
    family: str
    objective: str
    context: str = ""
    lineage_id: str = ""
    depends_on_task_ids: tuple[str, ...] = ()
    retry_of_task_id: str | None = None
    max_steps: int = 12
    max_seconds: float = 180.0

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.family.strip() or not self.objective.strip():
            raise ValueError("experiment task identity, family and objective are required")
        if not self.lineage_id.strip():
            object.__setattr__(self, "lineage_id", self.task_id)
        if isinstance(self.max_steps, bool) or not isinstance(self.max_steps, int) or self.max_steps <= 0:
            raise ValueError("experiment task max_steps must be a positive integer")
        if (
            isinstance(self.max_seconds, bool)
            or not isinstance(self.max_seconds, (int, float))
            or not math.isfinite(self.max_seconds)
            or self.max_seconds <= 0
        ):
            raise ValueError("experiment task max_seconds must be finite and positive")
        if len(set(self.depends_on_task_ids)) != len(self.depends_on_task_ids):
            raise ValueError("experiment task dependencies must be unique")
        if self.task_id in self.depends_on_task_ids or self.retry_of_task_id == self.task_id:
            raise ValueError("experiment task cannot depend on or retry itself")


def validate_task_graph(
    tasks: tuple[ExperimentTaskSpec, ...],
    *,
    selected_ids: tuple[str, ...] = (),
) -> tuple[ExperimentTaskSpec, ...]:
    """Validate and topologically order an immutable task graph.

    Selection is an execution cut.  It must contain the complete prerequisite
    closure so a backend never silently starts from an unproven task state.
    """

    if not tasks:
        raise ValueError("experiment task graph is empty")
    by_id: dict[str, ExperimentTaskSpec] = {}
    for task in tasks:
        if task.task_id in by_id:
            raise ValueError(f"duplicate experiment task_id: {task.task_id}")
        by_id[task.task_id] = task
    selected = tuple(selected_ids)
    if len(selected) != len(set(selected)):
        raise ValueError("selected experiment task ids must be unique")
    missing_selected = tuple(task_id for task_id in selected if task_id not in by_id)
    if missing_selected:
        raise ValueError(f"selected experiment task ids are missing: {missing_selected}")
    for task in tasks:
        references = task.depends_on_task_ids + ((task.retry_of_task_id,) if task.retry_of_task_id else ())
        unknown = tuple(reference for reference in references if reference not in by_id)
        if unknown:
            raise ValueError(f"task {task.task_id} references unknown tasks: {unknown}")

    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[ExperimentTaskSpec] = []

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise ValueError(f"experiment task dependency cycle includes {task_id}")
        visiting.add(task_id)
        task = by_id[task_id]
        for dependency in task.depends_on_task_ids:
            visit(dependency)
        if task.retry_of_task_id:
            visit(task.retry_of_task_id)
        visiting.remove(task_id)
        visited.add(task_id)
        ordered.append(task)

    for task in tasks:
        visit(task.task_id)
    if not selected:
        return tuple(ordered)

    selected_set = set(selected)
    required = tuple(
        dependency
        for task_id in selected
        for dependency in by_id[task_id].depends_on_task_ids
        + ((by_id[task_id].retry_of_task_id,) if by_id[task_id].retry_of_task_id else ())
        if dependency not in selected_set
    )
    if required:
        raise ValueError(f"selected task ids omit prerequisites: {tuple(dict.fromkeys(required))}")
    return tuple(task for task in ordered if task.task_id in selected_set)


__all__ = ["ExperimentTaskSpec", "validate_task_graph"]
