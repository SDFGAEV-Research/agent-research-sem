from __future__ import annotations

import json

from research_platform.reliability.diagnostics.api import (
    DiagnosticObjectRecord,
    OperationInvocationRecord,
    StateWriterRecord,
)
from research_platform.reliability.forensics.providers.index_db import ForensicIndexDB
from research_platform.reliability.forensics.providers.operation_index import (
    operation_invocation as read_operation_invocation,
    operations_open_at as read_operations_open_at,
    unclosed_operations as read_unclosed_operations,
)


_OBJECT_COLUMNS = (
    "object_id",
    "kind",
    "run_id",
    "task_id",
    "decision_cycle_id",
    "trace_id",
    "span_id",
    "component_id",
    "timestamp",
    "payload_json",
)
_OBJECT_SELECT = ",".join(_OBJECT_COLUMNS)

_STATE_COLUMNS = (
    "mutation_id",
    "state_name",
    "run_id",
    "task_id",
    "decision_cycle_id",
    "trace_id",
    "span_id",
    "component_id",
    "operation_id",
    "new_version",
    "new_digest",
    "timestamp",
    "payload_json",
)
_STATE_SELECT = ",".join(_STATE_COLUMNS)


def _decode_payload(raw: object, *, record_kind: str) -> dict[str, object]:
    payload = json.loads(str(raw))
    if not isinstance(payload, dict):
        raise ValueError(f"{record_kind} payload must decode to an object")
    return payload


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _object_record(row: tuple[object, ...]) -> DiagnosticObjectRecord:
    if len(row) != len(_OBJECT_COLUMNS):
        raise ValueError("diagnostic object projection row has invalid width")
    (
        object_id,
        kind,
        run_id,
        task_id,
        decision_cycle_id,
        trace_id,
        span_id,
        component_id,
        timestamp,
        payload_json,
    ) = row
    return DiagnosticObjectRecord(
        object_id=str(object_id),
        kind=str(kind),
        run_id=_optional_text(run_id),
        task_id=_optional_text(task_id),
        decision_cycle_id=_optional_text(decision_cycle_id),
        trace_id=_optional_text(trace_id),
        span_id=_optional_text(span_id),
        component_id=_optional_text(component_id),
        timestamp=None if timestamp is None else float(timestamp),
        payload=_decode_payload(payload_json, record_kind="diagnostic object"),
    )


def _state_writer_record(row: tuple[object, ...]) -> StateWriterRecord:
    if len(row) != len(_STATE_COLUMNS):
        raise ValueError("state-writer projection row has invalid width")
    (
        mutation_id,
        state_name,
        run_id,
        task_id,
        decision_cycle_id,
        trace_id,
        span_id,
        component_id,
        operation_id,
        new_version,
        new_digest,
        timestamp,
        payload_json,
    ) = row
    return StateWriterRecord(
        mutation_id=str(mutation_id),
        state_name=str(state_name),
        run_id=str(run_id),
        task_id=_optional_text(task_id),
        decision_cycle_id=_optional_text(decision_cycle_id),
        trace_id=_optional_text(trace_id),
        span_id=_optional_text(span_id),
        component_id=str(component_id),
        operation_id=str(operation_id),
        new_version=int(new_version),
        new_digest=str(new_digest),
        timestamp=float(timestamp),
        payload=_decode_payload(payload_json, record_kind="state writer"),
    )


class ForensicIndexReadSession:
    """One SQLite read connection for a compound diagnostic query."""

    def __init__(self, db: ForensicIndexDB) -> None:
        self.db = db
        self.conn = db.connect()
        self._closed = False

    def freshness(self) -> dict[str, tuple[int, str]]:
        rows = self.conn.execute(
            "SELECT ledger,rows,tail_hash FROM ledger_freshness ORDER BY ledger"
        ).fetchall()
        return {str(name): (int(count), str(tail)) for name, count, tail in rows}

    def locate(self, object_id: str) -> DiagnosticObjectRecord | None:
        row = self.conn.execute(
            f"SELECT {_OBJECT_SELECT} FROM object_index WHERE object_id=?",
            (object_id,),
        ).fetchone()
        return _object_record(row) if row else None

    def last_writer(self, run_id: str, state_name: str) -> StateWriterRecord | None:
        row = self.conn.execute(
            f"SELECT {_STATE_SELECT} FROM state_writers "
            "WHERE run_id=? AND state_name=? ORDER BY timestamp DESC LIMIT 1",
            (run_id, state_name),
        ).fetchone()
        return _state_writer_record(row) if row else None

    def around(
        self,
        *,
        run_id: str,
        timestamp: float,
        seconds: float = 30.0,
    ) -> tuple[DiagnosticObjectRecord, ...]:
        rows = self.conn.execute(
            f"SELECT {_OBJECT_SELECT} FROM object_index "
            "WHERE run_id=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (run_id, timestamp - seconds, timestamp + seconds),
        ).fetchall()
        return tuple(_object_record(row) for row in rows)

    def recent_state_writers(
        self,
        *,
        run_id: str,
        before: float,
        limit: int = 12,
    ) -> tuple[StateWriterRecord, ...]:
        if limit <= 0:
            return ()
        rows = self.conn.execute(
            f"SELECT {_STATE_SELECT} FROM state_writers "
            "WHERE run_id=? AND timestamp<=? ORDER BY timestamp DESC LIMIT ?",
            (run_id, before, limit),
        ).fetchall()
        return tuple(_state_writer_record(row) for row in rows)

    def related_to(
        self,
        object_id: str,
        *,
        limit: int = 100,
    ) -> tuple[DiagnosticObjectRecord, ...]:
        if limit <= 0:
            return ()
        row = self.conn.execute(
            "SELECT run_id,task_id,decision_cycle_id,trace_id,span_id "
            "FROM object_index WHERE object_id=?",
            (object_id,),
        ).fetchone()
        if row is None:
            return ()
        run_id, task_id, decision_cycle_id, trace_id, span_id = row
        rows = self.conn.execute(
            f"SELECT {_OBJECT_SELECT} FROM object_index WHERE run_id=? AND ("
            "(? IS NOT NULL AND task_id=?) OR "
            "(? IS NOT NULL AND decision_cycle_id=?) OR "
            "(? IS NOT NULL AND trace_id=?) OR "
            "(? IS NOT NULL AND span_id=?) OR object_id=?) "
            "ORDER BY timestamp LIMIT ?",
            (
                run_id,
                task_id,
                task_id,
                decision_cycle_id,
                decision_cycle_id,
                trace_id,
                trace_id,
                span_id,
                span_id,
                object_id,
                limit,
            ),
        ).fetchall()
        return tuple(_object_record(item) for item in rows)

    def operation_invocation(self, invocation_id: str) -> OperationInvocationRecord | None:
        return read_operation_invocation(self.conn, invocation_id)

    def unclosed_operations(
        self,
        *,
        run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[OperationInvocationRecord, ...]:
        return read_unclosed_operations(self.conn, run_id=run_id, limit=limit)

    def operations_open_at(
        self,
        *,
        run_id: str,
        timestamp: float,
        limit: int = 100,
    ) -> tuple[OperationInvocationRecord, ...]:
        return read_operations_open_at(
            self.conn,
            run_id=run_id,
            timestamp=timestamp,
            limit=limit,
        )

    def close(self) -> None:
        if not self._closed:
            self.conn.close()
            self._closed = True

    def __enter__(self) -> ForensicIndexReadSession:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class ForensicIndexReader:
    """Pure query model with one-shot methods plus explicit compound-query sessions."""

    def __init__(self, db: ForensicIndexDB) -> None:
        self.db = db

    def session(self) -> ForensicIndexReadSession:
        return ForensicIndexReadSession(self.db)

    def freshness(self) -> dict[str, tuple[int, str]]:
        with self.session() as session:
            return session.freshness()

    def locate(self, object_id: str) -> DiagnosticObjectRecord | None:
        with self.session() as session:
            return session.locate(object_id)

    def last_writer(self, run_id: str, state_name: str) -> StateWriterRecord | None:
        with self.session() as session:
            return session.last_writer(run_id, state_name)

    def around(
        self,
        *,
        run_id: str,
        timestamp: float,
        seconds: float = 30.0,
    ) -> tuple[DiagnosticObjectRecord, ...]:
        with self.session() as session:
            return session.around(run_id=run_id, timestamp=timestamp, seconds=seconds)

    def recent_state_writers(
        self,
        *,
        run_id: str,
        before: float,
        limit: int = 12,
    ) -> tuple[StateWriterRecord, ...]:
        with self.session() as session:
            return session.recent_state_writers(run_id=run_id, before=before, limit=limit)

    def related_to(
        self,
        object_id: str,
        *,
        limit: int = 100,
    ) -> tuple[DiagnosticObjectRecord, ...]:
        with self.session() as session:
            return session.related_to(object_id, limit=limit)

    def operation_invocation(self, invocation_id: str) -> OperationInvocationRecord | None:
        with self.session() as session:
            return session.operation_invocation(invocation_id)

    def unclosed_operations(
        self,
        *,
        run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[OperationInvocationRecord, ...]:
        with self.session() as session:
            return session.unclosed_operations(run_id=run_id, limit=limit)

    def operations_open_at(
        self,
        *,
        run_id: str,
        timestamp: float,
        limit: int = 100,
    ) -> tuple[OperationInvocationRecord, ...]:
        with self.session() as session:
            return session.operations_open_at(
                run_id=run_id,
                timestamp=timestamp,
                limit=limit,
            )


__all__ = ["ForensicIndexReadSession", "ForensicIndexReader"]
