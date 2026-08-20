from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from threading import RLock

from .sqlite_reader import TelemetryReadSession
from .sqlite_schema import initialize_telemetry_schema
from .sqlite_writer import TelemetryWriteSession


class TelemetrySQLiteBackend:
    """Connection/composition façade for telemetry SQLite persistence."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = RLock()
        with closing(self.connect()) as db:
            initialize_telemetry_schema(db)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def writer_session(self) -> TelemetryWriteSession:
        # Route through self.connect so tracing/fault injection observes the real boundary.
        return TelemetryWriteSession(self.connect, self._write_lock)

    def reader_session(self) -> TelemetryReadSession:
        return TelemetryReadSession(self.connect)

    def insert_many(self, values: tuple[tuple[object, ...], ...]) -> tuple[int, ...]:
        with self.writer_session() as session:
            return session.insert_many(values)

    def query(
        self,
        *,
        run_id: str,
        metric: str | None,
        decision_cycle_id: str | None,
        limit: int,
    ) -> tuple[tuple[object, ...], ...]:
        with self.reader_session() as session:
            return session.query(
                run_id=run_id,
                metric=metric,
                decision_cycle_id=decision_cycle_id,
                limit=limit,
            )

    def count(self) -> int:
        with self.reader_session() as session:
            return session.count()


__all__ = ["TelemetrySQLiteBackend", "TelemetryWriteSession", "TelemetryReadSession"]
