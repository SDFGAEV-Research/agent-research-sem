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
