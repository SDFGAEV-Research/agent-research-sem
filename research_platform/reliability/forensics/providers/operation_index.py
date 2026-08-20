from __future__ import annotations

import json
import sqlite3


_OPEN_COLUMNS = (
    "invocation_id",
    "operation_id",
    "operation_type",
    "run_id",
    "task_id",
    "decision_cycle_id",
    "trace_id",
    "span_id",
    "caller_component_id",
    "target_component_id",
    "started_event_id",
    "started_at",
    "terminal_event_id",
    "terminal_event_type",
    "terminal_at",
    "status",
    "failure_id",
)
_OPEN_SELECT = ",".join(_OPEN_COLUMNS)


def _rows_to_dicts(rows: list[tuple[object, ...]]) -> tuple[dict[str, object], ...]:
    return tuple(dict(zip(_OPEN_COLUMNS, row, strict=True)) for row in rows)


def operation_invocation(conn: sqlite3.Connection, invocation_id: str) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT latest_payload_json FROM operation_invocations WHERE invocation_id=?",
        (invocation_id,),
    ).fetchone()
    return json.loads(row[0]) if row else None


def unclosed_operations(
    conn: sqlite3.Connection,
    *,
    run_id: str | None = None,
    limit: int = 100,
) -> tuple[dict[str, object], ...]:
    if limit <= 0:
        return ()
    where = "started_at IS NOT NULL AND terminal_at IS NULL"
    args: tuple[object, ...]
    if run_id is None:
        args = (limit,)
    else:
        where += " AND run_id=?"
        args = (run_id, limit)
    rows = conn.execute(
        f"SELECT {_OPEN_SELECT} FROM operation_invocations "
        f"WHERE {where} ORDER BY started_at DESC LIMIT ?",
        args,
    ).fetchall()
    return _rows_to_dicts(rows)


def operations_open_at(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    timestamp: float,
    limit: int = 100,
) -> tuple[dict[str, object], ...]:
    """Return invocations that were open at an exact historical instant.

    This is temporal correlation, not proof that an open invocation caused a failure.
    """
    if limit <= 0:
        return ()
    rows = conn.execute(
        f"SELECT {_OPEN_SELECT} FROM operation_invocations "
        "WHERE run_id=? AND started_at IS NOT NULL AND started_at<=? "
        "AND (terminal_at IS NULL OR terminal_at>?) "
        "ORDER BY started_at DESC LIMIT ?",
        (run_id, timestamp, timestamp, limit),
    ).fetchall()
    return _rows_to_dicts(rows)


__all__ = ["operation_invocation", "unclosed_operations", "operations_open_at"]
