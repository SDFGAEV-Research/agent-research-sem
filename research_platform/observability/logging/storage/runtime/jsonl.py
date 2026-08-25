from __future__ import annotations

"""Durable append-only structured log storage.

The logging system owns records and queries; this adapter owns only the
storage protocol.  Each append is a complete JSON line followed by an fsync,
so a restart can recover every complete record without reconstructing an
in-memory log from the application process.
"""

import json
import os
from pathlib import Path
from threading import RLock
from typing import ClassVar

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.query.api import LogQueryPort
from research_platform.observability.logging.record.api import LogLevel, LogRecord
from research_platform.observability.logging.sink.api import LogSinkPort
from research_platform.scope.api import ScopeIdentity, ScopeKind
from research_platform.platform.kernel.durability.durable_file import durable_replace_file, durable_unlink


class JsonlLogCorruptionError(ValueError):
    """A complete JSONL record is corrupt and cannot be safely ignored."""


class JsonlLogStore(LogSinkPort, LogQueryPort):
    """Crash-tolerant structured log store with deterministic query order."""

    SCHEMA_VERSION: ClassVar[str] = "research-platform.log-record.v1"

    def __init__(self, path: str | Path, *, max_bytes: int = 64 * 1024 * 1024, max_segments: int = 8) -> None:
        if max_bytes <= 0:
            raise ValueError("JSONL log max_bytes must be positive")
        if max_segments <= 0:
            raise ValueError("JSONL log max_segments must be positive")
        self.path = Path(path).expanduser().resolve()
        self.max_bytes = max_bytes
        self.max_segments = max_segments
        self._lock = RLock()
        self._last_query_diagnostics: dict[str, int | bool] = {
            "corrupt_complete_lines": 0,
            "partial_tail_ignored": False,
            "scanned_lines": 0,
            "rotated_segments": 0,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def last_query_diagnostics(self) -> dict[str, int | bool]:
        return dict(self._last_query_diagnostics)

    def append(self, record: LogRecord) -> None:
        encoded = json.dumps(_encode_record(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._lock:
            self._rotate_if_needed(len(encoded.encode("utf-8")) + 1)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())

    def _segments(self) -> tuple[Path, ...]:
        rotated: list[tuple[int, Path]] = []
        prefix = self.path.name + "."
        for path in self.path.parent.glob(prefix + "*"):
            suffix = path.name[len(prefix):]
            if suffix.isdigit():
                rotated.append((int(suffix), path))
        return tuple([self.path] + [path for _, path in sorted(rotated, reverse=True)])

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if not self.path.is_file() or self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        for index in range(self.max_segments - 1, 0, -1):
            source = self.path.with_name(f"{self.path.name}.{index}")
            destination = self.path.with_name(f"{self.path.name}.{index + 1}")
            if source.exists():
                if index == self.max_segments - 1:
                    durable_unlink(destination)
                else:
                    durable_replace_file(source, destination)
        durable_replace_file(self.path, self.path.with_name(f"{self.path.name}.1"))

    def _append_record(self, encoded: str) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def query(
        self,
        *,
        scope: ScopeIdentity | None = None,
        system: SystemIdentity | None = None,
        component_id: str | None = None,
        trace_id: str | None = None,
        level_at_least: LogLevel | None = None,
        event: str | None = None,
        limit: int = 1000,
    ) -> tuple[LogRecord, ...]:
        if limit <= 0 or not self.path.is_file():
            return ()
        rank = {level: index for index, level in enumerate(LogLevel)}
        selected: list[LogRecord] = []
        corrupt_complete_lines = 0
        partial_tail_ignored = False
        scanned_lines = 0
        with self._lock:
            segments = tuple(path for path in self._segments() if path.is_file())
            for segment in segments:
                with segment.open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        scanned_lines += 1
                        if not line.strip():
                            continue
                        try:
                            row = _decode_record(json.loads(line))
                        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
                            if not line.endswith("\n"):
                                partial_tail_ignored = True
                                continue
                            corrupt_complete_lines += 1
                            raise JsonlLogCorruptionError(
                                f"corrupt complete JSONL record at line {line_number}: {segment}"
                            )
                        address = row.address
                        if scope is not None and scope not in address.scope_path:
                            continue
                        if system is not None and system not in address.system_path:
                            continue
                        if component_id is not None and address.component_id != component_id:
                            continue
                        if trace_id is not None and address.trace_id != trace_id:
                            continue
                        if level_at_least is not None and rank[row.level] < rank[level_at_least]:
                            continue
                        if event is not None and row.event != event:
                            continue
                        selected.append(row)
                        if len(selected) >= limit:
                            break
                if len(selected) >= limit:
                    break
        self._last_query_diagnostics = {
            "corrupt_complete_lines": corrupt_complete_lines,
            "partial_tail_ignored": partial_tail_ignored,
            "scanned_lines": scanned_lines,
            "rotated_segments": max(0, len(segments) - 1),
        }
        selected.sort(key=lambda row: (row.created_at, row.log_id), reverse=True)
        return tuple(selected[:limit])


def _encode_record(record: LogRecord) -> dict[str, object]:
    return {
        "schema_version": JsonlLogStore.SCHEMA_VERSION,
        "log_id": record.log_id,
        "created_at": record.created_at,
        "level": record.level.value,
        "logger": record.logger,
        "event": record.event,
        "message": record.message,
        "address": {
            "scope_path": [{"kind": item.kind.value, "scope_id": item.scope_id} for item in record.address.scope_path],
            "system_path": [{"system_id": item.system_id, "subsystem_path": list(item.subsystem_path)} for item in record.address.system_path],
            "component_id": record.address.component_id,
            "operation_id": record.address.operation_id,
            "trace_id": record.address.trace_id,
            "span_id": record.address.span_id,
        },
        "attributes": [list(item) for item in record.attributes],
        "exception": None if record.exception is None else {
            "error_type": record.exception.error_type,
            "qualified_type": record.exception.qualified_type,
            "safe_message": record.exception.safe_message,
            "error_digest": record.exception.error_digest,
        },
        "correlation_refs": list(record.correlation_refs),
        "failure_refs": list(record.failure_refs),
        "artifact_refs": list(record.artifact_refs),
    }


def _decode_record(document: object) -> LogRecord:
    if not isinstance(document, dict):
        raise TypeError("log line must be an object")
    address = document["address"]
    if not isinstance(address, dict):
        raise TypeError("log address must be an object")
    scopes = tuple(
        ScopeIdentity(ScopeKind(item["kind"]), str(item["scope_id"]))
        for item in address["scope_path"]
    )
    systems = tuple(
        SystemIdentity(str(item["system_id"]), tuple(str(value) for value in item.get("subsystem_path", ())))
        for item in address.get("system_path", ())
    )
    exception = document.get("exception")
    descriptor = None
    if exception is not None:
        from research_platform.platform.kernel.errors.contracts import SafeExceptionDescriptor

        descriptor = SafeExceptionDescriptor(
            str(exception["error_type"]),
            str(exception["qualified_type"]),
            str(exception["safe_message"]),
            str(exception["error_digest"]),
        )
    return LogRecord(
        log_id=str(document["log_id"]),
        created_at=float(document["created_at"]),
        level=LogLevel(str(document["level"])),
        logger=str(document["logger"]),
        event=str(document["event"]),
        message=str(document["message"]),
        address=DiagnosticAddress(
            scope_path=scopes,
            system_path=systems,
            component_id=address.get("component_id"),
            operation_id=address.get("operation_id"),
            trace_id=address.get("trace_id"),
            span_id=address.get("span_id"),
        ),
        attributes=tuple((str(item[0]), str(item[1])) for item in document.get("attributes", ())),
        exception=descriptor,
        correlation_refs=tuple(str(item) for item in document.get("correlation_refs", ())),
        failure_refs=tuple(str(item) for item in document.get("failure_refs", ())),
        artifact_refs=tuple(str(item) for item in document.get("artifact_refs", ())),
    )


__all__ = ["JsonlLogCorruptionError", "JsonlLogStore"]
