from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock
import time

from research_platform.execution.operation.api import OperationId
from research_platform.execution.workflow.api.progress import (
    WorkflowOperationBinding,
    WorkflowProgress,
    WorkflowProgressConflict,
    WorkflowProgressCorruption,
    WorkflowRunId,
)

_INITIALIZE_LOCK = Lock()


class SQLiteWorkflowProgressStore:
    """SQLite WAL authority for exact workflow step/operation ancestry."""

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
                        db.execute("""CREATE TABLE IF NOT EXISTS workflow_progress (
                            workflow_run_id TEXT PRIMARY KEY,
                            graph_digest TEXT NOT NULL,
                            version INTEGER NOT NULL,
                            completed_json TEXT NOT NULL,
                            running_json TEXT NOT NULL,
                            uncertain_json TEXT NOT NULL,
                            failed_json TEXT,
                            cancellation_requested INTEGER NOT NULL,
                            cancellation_reason TEXT
                        )""")
                        columns = tuple(row[1] for row in db.execute("PRAGMA table_info(workflow_progress)"))
                        expected = (
                            "workflow_run_id", "graph_digest", "version", "completed_json", "running_json",
                            "uncertain_json", "failed_json", "cancellation_requested", "cancellation_reason",
                        )
                        if columns != expected:
                            raise WorkflowProgressCorruption(
                                "workflow progress schema does not match current durable contract"
                            )
                    return
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.01)

    @staticmethod
    def _json_list(value: object, *, field: str) -> list[object]:
        if not isinstance(value, str):
            raise WorkflowProgressCorruption(f"workflow {field} must be JSON text")
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise WorkflowProgressCorruption(f"workflow {field} contains invalid JSON") from exc
        if not isinstance(decoded, list):
            raise WorkflowProgressCorruption(f"workflow {field} must decode to a list")
        return decoded

    @classmethod
    def _bindings(cls, value: object, *, field: str) -> tuple[WorkflowOperationBinding, ...]:
        rows = cls._json_list(value, field=field)
        bindings: list[WorkflowOperationBinding] = []
        for row in rows:
            if not isinstance(row, list) or len(row) != 2 or not all(isinstance(item, str) for item in row):
                raise WorkflowProgressCorruption(f"workflow {field} binding must be [step_id, operation_id]")
            bindings.append(WorkflowOperationBinding(row[0], OperationId(row[1])))
        return tuple(bindings)

    @classmethod
    def _failed_binding(cls, value: object) -> WorkflowOperationBinding | None:
        if value is None:
            return None
        rows = cls._json_list(value, field="failed_json")
        if len(rows) != 1:
            raise WorkflowProgressCorruption("workflow failed_json must contain exactly one binding")
        row = rows[0]
        if not isinstance(row, list) or len(row) != 2 or not all(isinstance(item, str) for item in row):
            raise WorkflowProgressCorruption("workflow failed_json binding must be [step_id, operation_id]")
        return WorkflowOperationBinding(row[0], OperationId(row[1]))

    @staticmethod
    def _binding_json(bindings: tuple[WorkflowOperationBinding, ...]) -> str:
        return json.dumps(
            [[item.step_id, item.operation_id.value] for item in bindings],
            separators=(",", ":"),
        )

    @classmethod
    def _decode(cls, row: tuple[object, ...]) -> WorkflowProgress:
        if not isinstance(row, tuple) or len(row) != 9:
            raise WorkflowProgressCorruption("workflow progress row shape is invalid")
        if not isinstance(row[0], str) or not isinstance(row[1], str):
            raise WorkflowProgressCorruption("workflow identity/digest columns must be text")
        if not isinstance(row[2], int) or isinstance(row[2], bool):
            raise WorkflowProgressCorruption("workflow progress version must be integer")
        if not isinstance(row[7], int) or row[7] not in (0, 1):
            raise WorkflowProgressCorruption("workflow cancellation flag must be 0 or 1")
        if row[8] is not None and not isinstance(row[8], str):
            raise WorkflowProgressCorruption("workflow cancellation_reason must be text or null")
        try:
            return WorkflowProgress(
                WorkflowRunId(row[0]),
                row[1],
                row[2],
                cls._bindings(row[3], field="completed_json"),
                cls._bindings(row[4], field="running_json"),
                cls._bindings(row[5], field="uncertain_json"),
                cls._failed_binding(row[6]),
                bool(row[7]),
                row[8],
            )
        except (TypeError, ValueError) as exc:
            raise WorkflowProgressCorruption("workflow progress row violates typed contract") from exc

    def _values(self, progress: WorkflowProgress) -> tuple[object, ...]:
        return (
            progress.workflow_run_id.value,
            progress.graph_digest,
            progress.version,
            self._binding_json(progress.completed),
            self._binding_json(progress.running),
            self._binding_json(progress.uncertain),
            None if progress.failed is None else self._binding_json((progress.failed,)),
            int(progress.cancellation_requested),
            progress.cancellation_reason,
        )

    def create(self, progress: WorkflowProgress) -> WorkflowProgress:
        try:
            with self._connect() as db:
                db.execute("INSERT INTO workflow_progress VALUES (?,?,?,?,?,?,?,?,?)", self._values(progress))
        except sqlite3.IntegrityError as exc:
            raise WorkflowProgressConflict(f"workflow already exists: {progress.workflow_run_id.value}") from exc
        return progress

    def load(self, workflow_run_id: WorkflowRunId) -> WorkflowProgress | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT workflow_run_id,graph_digest,version,completed_json,running_json,uncertain_json,"
                "failed_json,cancellation_requested,cancellation_reason FROM workflow_progress WHERE workflow_run_id=?",
                (workflow_run_id.value,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def compare_and_swap(self, expected_version: int, progress: WorkflowProgress) -> WorkflowProgress:
        values = self._values(progress)
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE workflow_progress SET graph_digest=?,version=?,completed_json=?,running_json=?,
                uncertain_json=?,failed_json=?,cancellation_requested=?,cancellation_reason=?
                WHERE workflow_run_id=? AND version=?""",
                (
                    values[1], values[2], values[3], values[4], values[5], values[6], values[7], values[8],
                    values[0], expected_version,
                ),
            )
            if cursor.rowcount != 1:
                raise WorkflowProgressConflict(f"workflow version conflict: {progress.workflow_run_id.value}")
        return progress


__all__ = ["SQLiteWorkflowProgressStore"]
