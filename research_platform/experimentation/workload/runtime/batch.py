from __future__ import annotations

from dataclasses import dataclass
import math

from research_platform.experimentation.experiment.api import (
    ExperimentWorkloadFailure,
    FailureScope,
    validate_task_graph,
)
from research_platform.platform.kernel import ExecutionContext

from ..api import WorkloadBatchBindingPort, WorkloadExecutionCutObserverPort, WorkloadTaskResult


class WorkloadBatchCloseError(RuntimeError):
    """A batch failed and its binding could not close cleanly."""

    def __init__(self, primary: BaseException, cleanup: BaseException) -> None:
        super().__init__("workload batch failed and binding close failed")
        self.primary = primary
        self.cleanup = cleanup


@dataclass(frozen=True, slots=True)
class WorkloadBatchResult:
    """Environment-neutral receipt for one ordered task batch."""

    task_results: tuple[WorkloadTaskResult, ...]

    @property
    def success_rate(self) -> float:
        return sum(result.success for result in self.task_results) / max(1, len(self.task_results))

    @property
    def utility_mean(self) -> float:
        return sum(result.utility for result in self.task_results) / max(1, len(self.task_results))

    @property
    def total_steps(self) -> int:
        return sum(result.steps for result in self.task_results)

    @property
    def total_duration_s(self) -> float:
        return sum(result.duration_s for result in self.task_results)

    @property
    def memory_queries(self) -> int:
        return sum(result.memory_queries for result in self.task_results)

    @property
    def blocked_count(self) -> int:
        return sum(result.blocked for result in self.task_results)

    @property
    def failed_count(self) -> int:
        return sum(not result.success and not result.blocked for result in self.task_results)


class GenericWorkloadBatchExecutor:
    """Reusable task-graph executor; adapters own only binding and result policy."""

    def __init__(self, cut_observer: WorkloadExecutionCutObserverPort | None = None) -> None:
        self._cut_observer = cut_observer

    def execute(self, binding: WorkloadBatchBindingPort) -> WorkloadBatchResult:
        tasks = validate_task_graph(tuple(binding.tasks))
        by_id: dict[str, WorkloadTaskResult] = {}
        results: list[WorkloadTaskResult] = []
        primary_error: BaseException | None = None
        try:
            for task in tasks:
                failed_dependencies = tuple(
                    dependency
                    for dependency in task.depends_on_task_ids
                    if dependency in by_id and not by_id[dependency].success
                )
                if failed_dependencies:
                    result = WorkloadTaskResult(
                        task_id=task.task_id,
                        family=task.family,
                        lineage_id=task.lineage_id,
                        success=False,
                        utility=0.0,
                        steps=0,
                        duration_s=0.0,
                        failure_reason="blocked_dependency",
                        blocked=True,
                        diagnostics={"blocked_by": failed_dependencies},
                    )
                else:
                    try:
                        result = binding.runner_for(task).run(task, binding.context)
                    except ExperimentWorkloadFailure as exc:
                        if exc.scope is not FailureScope.TASK:
                            raise
                        result = WorkloadTaskResult(
                            task_id=task.task_id,
                            family=task.family,
                            lineage_id=task.lineage_id,
                            success=False,
                            utility=0.0,
                            steps=0,
                            duration_s=0.0,
                            failure_reason=exc.code,
                            failure_scope=exc.scope.value,
                            diagnostics={
                                "phase": exc.phase,
                                "failure_scope": exc.scope.value,
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            },
                        )
                if not math.isfinite(float(result.utility)) or result.steps < 0:
                    raise ValueError(f"workload task result is invalid: {task.task_id}")
                binding.record_result(task=task, result=result, context=binding.context)
                results.append(result)
                by_id[task.task_id] = result
                if self._cut_observer is not None:
                    self._cut_observer.after_task(
                        task=task,
                        result=result,
                        completed_task_ids=tuple(item.task_id for item in results),
                        context=binding.context,
                    )
        except BaseException as exc:
            primary_error = exc

        try:
            binding.close()
        except BaseException as exc:
            if primary_error is not None:
                raise WorkloadBatchCloseError(primary_error, exc) from primary_error
            raise
        if primary_error is not None:
            raise primary_error
        return WorkloadBatchResult(tuple(results))


__all__ = ["GenericWorkloadBatchExecutor", "WorkloadBatchCloseError", "WorkloadBatchResult"]
