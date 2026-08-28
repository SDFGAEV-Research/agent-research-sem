from __future__ import annotations

import json
import math

from research_platform.experimentation.workload.api import WorkloadTaskResult
from research_platform.platform.kernel import canonical_bytes


class WorkloadProgressIntegrityError(RuntimeError):
    """A persisted workload-result prefix is malformed or inconsistent."""


_RESULT_FIELDS = frozenset(
    {
        "task_id",
        "family",
        "success",
        "utility",
        "steps",
        "duration_s",
        "lineage_id",
        "failure_reason",
        "memory_queries",
        "planner_actions",
        "decision_cycles",
        "completion_receipt",
        "blocked",
        "failure_scope",
        "diagnostics",
    }
)


def _require_string(row: dict[str, object], field: str) -> str:
    value = row[field]
    if type(value) is not str:
        raise TypeError(f"{field} must be a string")
    return value


def _require_bool(row: dict[str, object], field: str) -> bool:
    value = row[field]
    if type(value) is not bool:
        raise TypeError(f"{field} must be a boolean")
    return value


def _require_int(row: dict[str, object], field: str) -> int:
    value = row[field]
    if type(value) is not int:
        raise TypeError(f"{field} must be an integer")
    return value


def _require_finite_number(row: dict[str, object], field: str) -> float:
    value = row[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field} must be finite")
    return normalized


class WorkloadProgressCheckpointComponent:
    """Checkpoint component for the exact committed result prefix of a task batch."""

    component_id = "workload.progress"
    codec_id = "experimentation.workload.task-results.json"
    schema_version = "1"

    def __init__(self) -> None:
        self._results: tuple[WorkloadTaskResult, ...] = ()

    @property
    def results(self) -> tuple[WorkloadTaskResult, ...]:
        return self._results

    def replace(self, results: tuple[WorkloadTaskResult, ...]) -> None:
        normalized = tuple(results)
        ids = tuple(result.task_id for result in normalized)
        if any(not item.strip() for item in ids) or len(ids) != len(set(ids)):
            raise WorkloadProgressIntegrityError(
                "workload progress requires unique non-empty task ids"
            )
        self._results = normalized

    def capture(self) -> bytes:
        return canonical_bytes({"results": self._results})

    def restore(self, payload: bytes) -> None:
        try:
            document = json.loads(payload.decode("utf-8"))
            if not isinstance(document, dict) or set(document) != {"results"}:
                raise TypeError("workload progress document fields are not exact")
            rows = document["results"]
            if not isinstance(rows, list):
                raise TypeError("results must be a list")
            results = tuple(self._decode_result(row) for row in rows)
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise WorkloadProgressIntegrityError(
                "invalid workload progress checkpoint document"
            ) from exc
        self.replace(results)

    @staticmethod
    def _decode_result(row: object) -> WorkloadTaskResult:
        if not isinstance(row, dict) or set(row) != _RESULT_FIELDS:
            raise TypeError("workload progress result fields are not exact")
        planner_actions = row["planner_actions"]
        decision_cycles = row["decision_cycles"]
        diagnostics = row["diagnostics"]
        if not isinstance(planner_actions, list) or any(
            not isinstance(item, dict) for item in planner_actions
        ):
            raise TypeError("planner_actions must be a list of objects")
        if not isinstance(decision_cycles, list) or any(
            not isinstance(item, dict) for item in decision_cycles
        ):
            raise TypeError("decision_cycles must be a list of objects")
        if not isinstance(diagnostics, dict):
            raise TypeError("diagnostics must be an object")
        return WorkloadTaskResult(
            task_id=_require_string(row, "task_id"),
            family=_require_string(row, "family"),
            success=_require_bool(row, "success"),
            utility=_require_finite_number(row, "utility"),
            steps=_require_int(row, "steps"),
            duration_s=_require_finite_number(row, "duration_s"),
            lineage_id=_require_string(row, "lineage_id"),
            failure_reason=_require_string(row, "failure_reason"),
            memory_queries=_require_int(row, "memory_queries"),
            planner_actions=tuple(dict(item) for item in planner_actions),
            decision_cycles=tuple(dict(item) for item in decision_cycles),
            completion_receipt=row["completion_receipt"],
            blocked=_require_bool(row, "blocked"),
            failure_scope=_require_string(row, "failure_scope"),
            diagnostics=dict(diagnostics),
        )


__all__ = ["WorkloadProgressCheckpointComponent", "WorkloadProgressIntegrityError"]
