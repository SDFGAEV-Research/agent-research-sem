from __future__ import annotations

import pytest

from research_platform.experimentation.experiment.api import (
    ExperimentTaskSpec,
    ExperimentWorkloadFailure,
    FailureScope,
    validate_task_graph,
)


def test_generic_task_graph_orders_prerequisites_and_retries() -> None:
    ordered = validate_task_graph(
        (
            ExperimentTaskSpec("child", "task", "child", depends_on_task_ids=("root",)),
            ExperimentTaskSpec("retry", "task", "retry", retry_of_task_id="root"),
            ExperimentTaskSpec("root", "task", "root"),
        )
    )

    assert tuple(task.task_id for task in ordered) == ("root", "child", "retry")


def test_generic_task_graph_rejects_an_incomplete_execution_cut() -> None:
    with pytest.raises(ValueError, match="omit prerequisites"):
        validate_task_graph(
            (
                ExperimentTaskSpec("root", "task", "root"),
                ExperimentTaskSpec("child", "task", "child", depends_on_task_ids=("root",)),
            ),
            selected_ids=("child",),
        )


def test_failure_scope_controls_continuation() -> None:
    task_failure = ExperimentWorkloadFailure("decision", "TASK_FAILED", "bad task")
    branch_failure = ExperimentWorkloadFailure(
        "observe", "BRANCH_FAILED", "state lost", scope=FailureScope.BRANCH
    )

    assert task_failure.may_continue_with_next_task is True
    assert branch_failure.may_continue_with_next_task is False
