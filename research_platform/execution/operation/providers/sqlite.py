from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
import time

_INITIALIZE_LOCK = Lock()

from research_platform.execution.command.api import CommandId
from research_platform.execution.operation.api import (
    EffectId,
    OperationConflict,
    OperationCorruption,
    OperationEffectCertainty,
    OperationEffectProfile,
    OperationFailure,
    OperationFailureKind,
    OperationId,
    OperationSnapshot,
    OperationState,
)


class SQLiteOperationStore:
    """Durable operation lifecycle state; command intent remains a foreign authority."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @property
    def durability(self) -> str:
        return "sqlite-wal"

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=30.0, isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _initialize(self) -> None:
        deadline = time.monotonic() + 30.0
        with _INITIALIZE_LOCK:
            while True:
                try:
                    with self._connect() as db:
                        if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                            db.execute("PRAGMA journal_mode=WAL").fetchone()
                        db.execute(
                            """CREATE TABLE IF NOT EXISTS operations (
                            operation_id TEXT PRIMARY KEY,
                            command_id TEXT NOT NULL,
                            state TEXT NOT NULL,
                            version INTEGER NOT NULL,
                            created_at REAL NOT NULL,
                            updated_at REAL NOT NULL,
                            parent_operation_id TEXT,
                            effect_id TEXT,
                            effect_profile TEXT NOT NULL,
                            effect_certainty TEXT NOT NULL,
                            result_digest TEXT,
                            failure_kind TEXT,
                            failure_code TEXT,
                            failure_message TEXT,
                            failure_retryable INTEGER,
                            failure_reconciliation_required INTEGER,
                            cancellation_requested INTEGER NOT NULL,
                            cancellation_reason TEXT)"""
                        )
                        columns = tuple(row[1] for row in db.execute("PRAGMA table_info(operations)"))
                        expected = (
                            "operation_id", "command_id", "state", "version", "created_at", "updated_at",
                            "parent_operation_id", "effect_id", "effect_profile", "effect_certainty", "result_digest",
                            "failure_kind", "failure_code", "failure_message", "failure_retryable",
                            "failure_reconciliation_required", "cancellation_requested", "cancellation_reason",
                        )
                        if columns != expected:
                            raise OperationCorruption("operation schema does not match current durable contract")
                    return
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.01)

    @staticmethod
    def _from_row(row: tuple[object, ...]) -> OperationSnapshot:
        if not isinstance(row, tuple) or len(row) != 18:
            raise OperationCorruption("operation row shape is invalid")
        if not all(isinstance(row[index], str) for index in (0, 1, 2, 8, 9)):
            raise OperationCorruption("operation identity/state/effect columns must be text")
        if isinstance(row[3], bool) or not isinstance(row[3], int):
            raise OperationCorruption("operation version must be integer")
        for index, field in ((4, "created_at"), (5, "updated_at")):
            if isinstance(row[index], bool) or not isinstance(row[index], (int, float)):
                raise OperationCorruption(f"operation {field} must be numeric")
        for index, field in ((6, "parent_operation_id"), (7, "effect_id"), (10, "result_digest"), (17, "cancellation_reason")):
            if row[index] is not None and not isinstance(row[index], str):
                raise OperationCorruption(f"operation {field} must be text or null")
        if row[16] not in (0, 1):
            raise OperationCorruption("operation cancellation_requested must be 0 or 1")
        failure_columns = row[11:16]
        if row[11] is None:
            if any(value is not None for value in failure_columns):
                raise OperationCorruption("operation failure columns must be all null when failure_kind is null")
            failure = None
        else:
            if not all(isinstance(row[index], str) for index in (11, 12, 13)):
                raise OperationCorruption("operation failure kind/code/message must be text")
            if row[14] not in (0, 1) or row[15] not in (0, 1):
                raise OperationCorruption("operation failure booleans must be 0 or 1")
            try:
                failure = OperationFailure(OperationFailureKind(row[11]), row[12], row[13], bool(row[14]), bool(row[15]))
            except (TypeError, ValueError) as exc:
                raise OperationCorruption("operation failure columns violate typed contract") from exc
        try:
            return OperationSnapshot(
                OperationId(row[0]), CommandId(row[1]), OperationState(row[2]), row[3], float(row[4]), float(row[5]),
                None if row[6] is None else OperationId(row[6]),
                None if row[7] is None else EffectId(row[7]),
                OperationEffectProfile(row[8]), OperationEffectCertainty(row[9]), row[10], failure,
                bool(row[16]), row[17],
            )
        except (TypeError, ValueError) as exc:
            raise OperationCorruption("operation row violates typed lifecycle contract") from exc

    @staticmethod
    def _immutable_identity(snapshot: OperationSnapshot) -> tuple[object, ...]:
        return (
            snapshot.command_id,
            snapshot.parent_operation_id,
            snapshot.effect_id,
            snapshot.effect_profile,
        )

    def load(self, operation_id: OperationId) -> OperationSnapshot | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM operations WHERE operation_id=?",
                (operation_id.value,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    def create_or_get(self, snapshot: OperationSnapshot) -> tuple[OperationSnapshot, bool]:
        if snapshot.state is not OperationState.CREATED or snapshot.version != 0:
            raise ValueError("new durable operation must start at CREATED version 0")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM operations WHERE operation_id=?",
                (snapshot.operation_id.value,),
            ).fetchone()
            if row is not None:
                db.execute("COMMIT")
                existing = self._from_row(row)
                if self._immutable_identity(existing) != self._immutable_identity(snapshot):
                    raise OperationConflict(
                        f"operation identity reused with different immutable contract: {snapshot.operation_id.value}"
                    )
                return existing, False
            try:
                db.execute(
                    "INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        snapshot.operation_id.value,
                        snapshot.command_id.value,
                        snapshot.state.value,
                        snapshot.version,
                        snapshot.created_at_unix,
                        snapshot.updated_at_unix,
                        None if snapshot.parent_operation_id is None else snapshot.parent_operation_id.value,
                        None if snapshot.effect_id is None else snapshot.effect_id.value,
                        snapshot.effect_profile.value,
                        snapshot.effect_certainty.value,
                        snapshot.result_digest,
                        None,
                        None,
                        None,
                        None,
                        None,
                        int(snapshot.cancellation_requested),
                        snapshot.cancellation_reason,
                    ),
                )
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return snapshot, True

    @staticmethod
    def _update_values(snapshot: OperationSnapshot) -> tuple[object, ...]:
        failure = snapshot.failure
        return (
            snapshot.state.value,
            snapshot.version,
            snapshot.updated_at_unix,
            None if snapshot.parent_operation_id is None else snapshot.parent_operation_id.value,
            None if snapshot.effect_id is None else snapshot.effect_id.value,
            snapshot.effect_profile.value,
            snapshot.effect_certainty.value,
            snapshot.result_digest,
            None if failure is None else failure.kind.value,
            None if failure is None else failure.code,
            None if failure is None else failure.message,
            None if failure is None else int(failure.retryable),
            None if failure is None else int(failure.reconciliation_required),
            int(snapshot.cancellation_requested),
            snapshot.cancellation_reason,
            snapshot.operation_id.value,
        )

    def compare_and_swap(self, expected_version: int, snapshot: OperationSnapshot) -> OperationSnapshot:
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE operations SET state=?,version=?,updated_at=?,parent_operation_id=?,effect_id=?,effect_profile=?,
                effect_certainty=?,result_digest=?,failure_kind=?,failure_code=?,failure_message=?,failure_retryable=?,
                failure_reconciliation_required=?,cancellation_requested=?,cancellation_reason=?
                WHERE operation_id=? AND version=?""",
                self._update_values(snapshot) + (expected_version,),
            )
            if cursor.rowcount != 1:
                raise OperationConflict(f"operation version conflict: {snapshot.operation_id.value}")
        return snapshot


__all__ = ["SQLiteOperationStore"]
