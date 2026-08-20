from __future__ import annotations

import json

from ..api.rows import PendingMetric
from ..api.ports import StorageMetricRow

_QUERY_KEYS = (
    "sequence", "metric", "value", "timestamp", "run_id", "task_id",
    "decision_cycle_id", "trace_id", "span_id", "operation_id", "component_id",
    "participant_generations", "dimensions",
)


def encode_pending_metric(row: PendingMetric) -> StorageMetricRow:
    context = row.context
    dimensions = json.dumps(dict(row.dimensions), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    generations = json.dumps(dict(context.participant_generations), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        row.metric, row.value, row.timestamp, context.run_id, context.study_id, context.condition_id,
        context.task_id, context.decision_cycle_id, context.trace_id, context.span_id,
        context.operation_id, context.component_id, generations, dimensions,
    )


def decode_metric_query_row(row: StorageMetricRow) -> dict[str, object]:
    values = list(row)
    values[-2] = json.loads(str(values[-2]))
    values[-1] = json.loads(str(values[-1]))
    return dict(zip(_QUERY_KEYS, values))


__all__ = ["decode_metric_query_row", "encode_pending_metric"]
