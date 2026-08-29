from __future__ import annotations

from dataclasses import replace
import math

import pytest

from research_platform.experimentation.workload.api import WorkloadTaskResult


def _result() -> WorkloadTaskResult:
    return WorkloadTaskResult(
        task_id="task-1",
        family="family",
        success=True,
        utility=1.0,
        steps=1,
        duration_s=0.25,
        lineage_id="lineage-1",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("success", 1),
        ("blocked", 0),
        ("steps", True),
        ("memory_queries", False),
        ("utility", math.nan),
        ("duration_s", math.inf),
        ("duration_s", -0.1),
        ("failure_scope", "unknown"),
    ],
)
def test_workload_task_result_rejects_invalid_typed_state(field, value) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(_result(), **{field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"blocked": True},
        {"failure_reason": "unexpected_failure"},
        {"success": False},
        {"success": False, "blocked": True},
    ],
)
def test_workload_task_result_rejects_impossible_outcome_combinations(changes) -> None:
    with pytest.raises(ValueError):
        replace(_result(), **changes)


def test_workload_task_result_accepts_explicit_failed_and_blocked_outcomes() -> None:
    failed = replace(_result(), success=False, failure_reason="task_failed")
    blocked = replace(
        _result(), success=False, blocked=True, failure_reason="blocked_dependency"
    )
    assert not failed.success and not failed.blocked
    assert not blocked.success and blocked.blocked
