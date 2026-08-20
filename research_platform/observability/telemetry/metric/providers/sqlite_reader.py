from __future__ import annotations

import sqlite3
from typing import Callable


class TelemetryReadSession:
    """Explicit read connection for one or many operator queries."""

    def __init__(self, connect: Callable[[], sqlite3.Connection]) -> None:
        self.db = connect()
        self._closed = False

    def query(
        self,
        *,
        run_id: str,
        metric: str | None,
        decision_cycle_id: str | None,
        limit: int,
    ) -> tuple[tuple[object, ...], ...]:
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
            "SELECT sequence,metric,value,timestamp,run_id,task_id,"
            "decision_cycle_id,trace_id,span_id,operation_id,component_id,"
            "participant_generations_json,dimensions_json "
            "FROM metric_observations WHERE "
            + " AND ".join(clauses)
            + " ORDER BY sequence LIMIT ?"
        )
        return tuple(self.db.execute(sql, args).fetchall())

    def count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM metric_observations").fetchone()[0])

    def close(self) -> None:
        if not self._closed:
            self.db.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
