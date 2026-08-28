from __future__ import annotations

import json
import math

import pytest

from research_platform.experimentation.checkpoint.runtime.workload_progress import (
    WorkloadProgressCheckpointComponent,
    WorkloadProgressIntegrityError,
)
from research_platform.experimentation.workload.api import WorkloadTaskResult


def _result() -> WorkloadTaskResult:
    return WorkloadTaskResult(
        task_id="task-1",
        family="family",
        success=False,
        utility=0.25,
        steps=2,
        duration_s=1.5,
        lineage_id="lineage-1",
        failure_reason="expected_failure",
        memory_queries=3,
        planner_actions=({"action_type": "inspect"},),
        decision_cycles=({"decision_cycle_id": "cycle-1"},),
        blocked=False,
        diagnostics={"code": "EXPECTED"},
    )


def _document() -> dict[str, object]:
    component = WorkloadProgressCheckpointComponent()
    component.replace((_result(),))
    return json.loads(component.capture().decode("utf-8"))


def test_workload_progress_round_trip_preserves_typed_receipt() -> None:
    source = WorkloadProgressCheckpointComponent()
    source.replace((_result(),))
    restored = WorkloadProgressCheckpointComponent()
    restored.restore(source.capture())
    assert restored.results == (_result(),)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("success", "false"),
        ("blocked", 0),
        ("steps", "2"),
        ("memory_queries", 3.0),
        ("utility", "0.25"),
        ("duration_s", "1.5"),
    ],
)
def test_workload_progress_rejects_implicit_scalar_coercion(field, bad_value) -> None:
    document = _document()
    document["results"][0][field] = bad_value
    target = WorkloadProgressCheckpointComponent()
    with pytest.raises(WorkloadProgressIntegrityError):
        target.restore(json.dumps(document).encode("utf-8"))


def test_workload_progress_requires_exact_document_and_result_fields() -> None:
    document = _document()
    document["unexpected"] = True
    with pytest.raises(WorkloadProgressIntegrityError):
        WorkloadProgressCheckpointComponent().restore(
            json.dumps(document).encode("utf-8")
        )

    document = _document()
    document["results"][0]["unexpected"] = True
    with pytest.raises(WorkloadProgressIntegrityError):
        WorkloadProgressCheckpointComponent().restore(
            json.dumps(document).encode("utf-8")
        )


def test_workload_progress_rejects_non_finite_measurements() -> None:
    for field in ("utility", "duration_s"):
        document = _document()
        document["results"][0][field] = math.nan
        with pytest.raises(WorkloadProgressIntegrityError):
            WorkloadProgressCheckpointComponent().restore(
                json.dumps(document).encode("utf-8")
            )


def test_workload_progress_append_is_incremental_and_rejects_duplicate_task_ids() -> None:
    component = WorkloadProgressCheckpointComponent()
    first = _result()
    second = WorkloadTaskResult(
        task_id="task-2",
        family=first.family,
        success=True,
        utility=1.0,
        steps=1,
        duration_s=0.5,
        lineage_id="lineage-2",
    )

    component.append(first)
    component.append(second)
    assert component.results == (first, second)

    with pytest.raises(WorkloadProgressIntegrityError):
        component.append(first)
