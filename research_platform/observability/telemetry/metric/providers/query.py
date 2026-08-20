from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sqlite3


@dataclass(frozen=True, slots=True)
class MetricSummary:
    metric: str
    count: int
    minimum: float
    maximum: float
    mean: float
    p50: float
    p95: float
    p99: float


class SQLiteTelemetryReader:
    """Strictly read-only SQLite metric query backend."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        uri = f"file:{self.path.resolve().as_posix()}?mode=ro"
        db = sqlite3.connect(uri, uri=True, timeout=30)
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def query(
        self,
        *,
        run_id: str,
        metric: str | None = None,
        decision_cycle_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[dict[str, object], ...]:
        if limit <= 0:
            return ()
        clauses = ["run_id=?"]
        args: list[object] = [run_id]
        if metric is not None:
            clauses.append("metric=?")
            args.append(metric)
        if decision_cycle_id is not None:
            clauses.append("decision_cycle_id=?")
            args.append(decision_cycle_id)
        args.append(limit)
        sql = (
            "SELECT sequence,metric,value,timestamp,run_id,task_id,decision_cycle_id,trace_id,span_id,"
            "operation_id,component_id,dimensions_json FROM metric_observations WHERE "
            f"{' AND '.join(clauses)} ORDER BY sequence LIMIT ?"
        )
        with closing(self._connect()) as db:
            rows = db.execute(sql, args).fetchall()
        keys = (
            "sequence", "metric", "value", "timestamp", "run_id", "task_id", "decision_cycle_id",
            "trace_id", "span_id", "operation_id", "component_id", "dimensions",
        )
        result: list[dict[str, object]] = []
        for row in rows:
            values = list(row)
            values[-1] = json.loads(values[-1])
            result.append(dict(zip(keys, values)))
        return tuple(result)

    @staticmethod
    def _percentile(values: list[float], q: float) -> float:
        if not values:
            raise ValueError("empty metric sample")
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * q
        low = int(math.floor(position))
        high = int(math.ceil(position))
        if low == high:
            return ordered[low]
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    def summarize(self, *, run_id: str, metric: str) -> MetricSummary:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT value FROM metric_observations WHERE run_id=? AND metric=? ORDER BY sequence",
                (run_id, metric),
            ).fetchall()
        values = [float(row[0]) for row in rows]
        if not values:
            raise KeyError(f"no observations for run={run_id!r} metric={metric!r}")
        return MetricSummary(
            metric,
            len(values),
            min(values),
            max(values),
            sum(values) / len(values),
            self._percentile(values, .50),
            self._percentile(values, .95),
            self._percentile(values, .99),
        )


__all__ = ["MetricSummary", "SQLiteTelemetryReader"]
