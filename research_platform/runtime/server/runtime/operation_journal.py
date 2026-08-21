from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
from threading import Lock

from research_platform.platform.kernel.durability.file_lock import InterprocessFileLock
from research_platform.runtime.server.api import (
    ServerOperationFinished,
    ServerOperationJournalPort,
    ServerOperationStarted,
    ServerOperationKind,
    ServerOperationRecord,
    ServerOperationState,
)


class ServerOperationJournalIntegrityError(RuntimeError):
    """The durable server-operation ledger cannot be safely replayed."""


class JsonlServerOperationJournal(ServerOperationJournalPort):
    """Append-only local operation ledger for server control-plane actions.

    The ledger is controller-local and contains no credentials or raw remote
    commands.  It stores correlation IDs, request digests, timing, result
    classes and bounded output sizes, so a failed SSH operation can be
    diagnosed without making the server profile or command text a secret
    transport.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._guard_path = self.path.with_name(self.path.name + ".guard.lock")
        self._lock = Lock()

    def _append(self, event_type: str, event: object) -> None:
        payload = asdict(event)
        for key, value in tuple(payload.items()):
            if hasattr(value, "value"):
                payload[key] = value.value
        record = {"event": event_type, **payload}
        encoded = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        with self._lock:
            with InterprocessFileLock(self._guard_path):
                with self.path.open("ab") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())

    @staticmethod
    def _started(payload: dict[str, object]) -> ServerOperationStarted:
        try:
            return ServerOperationStarted(
                str(payload["operation_id"]),
                str(payload["server_id"]),
                ServerOperationKind(str(payload["kind"])),
                str(payload["request_digest"]),
                float(payload["started_at"]),
                bool(payload["interactive"]),
                str(payload.get("profile_digest", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation started record is malformed"
            ) from exc

    @staticmethod
    def _finished(payload: dict[str, object]) -> ServerOperationFinished:
        try:
            return ServerOperationFinished(
                str(payload["operation_id"]),
                str(payload["server_id"]),
                ServerOperationKind(str(payload["kind"])),
                str(payload["request_digest"]),
                ServerOperationState(str(payload["state"])),
                float(payload["finished_at"]),
                float(payload["duration_seconds"]),
                None if payload.get("return_code") is None else int(payload["return_code"]),
                str(payload["failure_kind"]),
                int(payload["stdout_bytes"]),
                int(payload["stderr_bytes"]),
                None if payload.get("error_type") is None else str(payload["error_type"]),
                None if payload.get("error_digest") is None else str(payload["error_digest"]),
                str(payload.get("profile_digest", "")),
                str(payload.get("stdout_digest", "")),
                str(payload.get("stderr_digest", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation finished record is malformed"
            ) from exc

    def _read_records(self) -> tuple[ServerOperationRecord, ...]:
        if not self.path.exists():
            return ()
        records: dict[str, ServerOperationRecord] = {}
        order: list[str] = []
        with self._lock:
            with InterprocessFileLock(self._guard_path):
                with self.path.open("rb") as stream:
                    for line_number, raw in enumerate(stream, start=1):
                        if not raw.strip():
                            continue
                        try:
                            payload = json.loads(raw.decode("utf-8"))
                            if not isinstance(payload, dict):
                                raise TypeError("event is not an object")
                            event_type = payload.pop("event")
                            if event_type == "started":
                                event = self._started(payload)
                                if event.operation_id in records:
                                    raise ValueError("duplicate operation start")
                                records[event.operation_id] = ServerOperationRecord(event)
                                order.append(event.operation_id)
                            elif event_type == "finished":
                                event = self._finished(payload)
                                record = records.get(event.operation_id)
                                if record is None or record.finished is not None:
                                    raise ValueError("finish has no unique open operation")
                                if (
                                    record.started.server_id != event.server_id
                                    or record.started.kind != event.kind
                                    or record.started.request_digest != event.request_digest
                                ):
                                    raise ValueError("finish does not match its start")
                                records[event.operation_id] = ServerOperationRecord(record.started, event)
                            else:
                                raise ValueError(f"unknown event type {event_type!r}")
                        except ServerOperationJournalIntegrityError as exc:
                            raise ServerOperationJournalIntegrityError(
                                f"server operation ledger is corrupt at line {line_number}"
                            ) from exc
                        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
                            raise ServerOperationJournalIntegrityError(
                                f"server operation ledger is corrupt at line {line_number}"
                            ) from exc
        return tuple(records[operation_id] for operation_id in order)

    def record_started(self, event: ServerOperationStarted) -> None:
        self._append("started", event)

    def record_finished(self, event: ServerOperationFinished) -> None:
        self._append("finished", event)

    def read_operation(self, operation_id: str) -> ServerOperationRecord | None:
        if not operation_id:
            raise ValueError("operation_id must be non-empty")
        return next(
            (record for record in self._read_records() if record.operation_id == operation_id),
            None,
        )

    def pending_operations(self) -> tuple[ServerOperationRecord, ...]:
        """Return operations with a durable start but no durable finish.

        This is a reconciliation signal, not a retry queue.  A caller must
        inspect the remote effect before submitting a mutating operation again.
        """

        return tuple(record for record in self._read_records() if record.effect_uncertain)

    def recent_operations(self, limit: int = 20) -> tuple[ServerOperationRecord, ...]:
        if limit <= 0:
            raise ValueError("operation history limit must be positive")
        records = self._read_records()
        return tuple(reversed(records[-limit:]))


__all__ = ["JsonlServerOperationJournal", "ServerOperationJournalIntegrityError"]
