from __future__ import annotations

import sqlite3
from threading import RLock
from typing import Callable


INSERT_SQL = """INSERT INTO metric_observations(
metric,value,timestamp,run_id,study_id,condition_id,task_id,decision_cycle_id,
trace_id,span_id,operation_id,component_id,participant_generations_json,
dimensions_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


class TelemetryWriteSession:
    """One persistent writer connection; batch commit is the hot persistence boundary."""

    def __init__(
        self,
        connect: Callable[[], sqlite3.Connection],
        write_lock: RLock,
    ) -> None:
        self._write_lock = write_lock
        self.db = connect()
        self._closed = False

    def insert_many(self, values: tuple[tuple[object, ...], ...]) -> tuple[int, ...]:
        if self._closed:
            raise RuntimeError("telemetry write session closed")
        if not values:
            return ()
        with self._write_lock, self.db:
            self.db.executemany(INSERT_SQL, values)
            end = int(self.db.execute("SELECT last_insert_rowid()").fetchone()[0])
            start = end - len(values) + 1
        return tuple(range(start, end + 1))

    def close(self) -> None:
        if not self._closed:
            self.db.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
