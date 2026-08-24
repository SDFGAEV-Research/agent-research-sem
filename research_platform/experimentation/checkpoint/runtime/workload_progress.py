from __future__ import annotations

import json

from research_platform.experimentation.workload.api import WorkloadTaskResult
from research_platform.platform.kernel import canonical_bytes


class WorkloadProgressIntegrityError(RuntimeError):
    """A persisted workload-result prefix is malformed or inconsistent."""


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
        if not isinstance(row, dict):
            raise TypeError("workload progress result rows must be objects")
        planner_actions = row.get("planner_actions", ())
        decision_cycles = row.get("decision_cycles", ())
        diagnostics = row.get("diagnostics", {})
        if not isinstance(planner_actions, list):
            raise TypeError("planner_actions must be a list")
        if not isinstance(decision_cycles, list):
            raise TypeError("decision_cycles must be a list")
        if not isinstance(diagnostics, dict):
            raise TypeError("diagnostics must be an object")
        if any(not isinstance(item, dict) for item in planner_actions):
            raise TypeError("planner action rows must be objects")
        if any(not isinstance(item, dict) for item in decision_cycles):
            raise TypeError("decision cycle rows must be objects")
        return WorkloadTaskResult(
            task_id=str(row["task_id"]),
            family=str(row["family"]),
            success=bool(row["success"]),
            utility=float(row["utility"]),
            steps=int(row["steps"]),
            duration_s=float(row["duration_s"]),
            lineage_id=str(row["lineage_id"]),
            failure_reason=str(row.get("failure_reason", "")),
            memory_queries=int(row.get("memory_queries", 0)),
            planner_actions=tuple(dict(item) for item in planner_actions),
            decision_cycles=tuple(dict(item) for item in decision_cycles),
            completion_receipt=row.get("completion_receipt"),
            blocked=bool(row.get("blocked", False)),
            failure_scope=str(row.get("failure_scope", "task")),
            diagnostics=dict(diagnostics),
        )


__all__ = ["WorkloadProgressCheckpointComponent", "WorkloadProgressIntegrityError"]
