from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import threading
import traceback

from ..api.diagnostics import RunDiagnosticsPort
from ..api.artifacts import RunArtifactKind, RunArtifactStorePort


def json_default(value: object) -> object:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    return repr(value)


def exception_chain(exception: BaseException) -> tuple[dict[str, str], ...]:
    chain: list[dict[str, str]] = []
    current: BaseException | None = exception
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append({"type": type(current).__name__, "message": str(current)})
        current = current.__cause__ or current.__context__
    return tuple(chain)


class JsonlAppender:
    """Durable append-only record provider for run-scoped JSONL artifacts."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def append(self, value: Mapping[str, object]) -> None:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=json_default)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())


class JsonlRunDiagnostics(RunDiagnosticsPort):
    """Platform implementation of the run diagnostics interface."""

    def __init__(self, artifacts: RunArtifactStorePort, *, run_id: str = "") -> None:
        self.events = JsonlAppender(Path(artifacts.path("events.jsonl", kind=RunArtifactKind.LOG)))
        self.metrics = JsonlAppender(Path(artifacts.path("metrics.jsonl", kind=RunArtifactKind.LOG)))
        self.failures = JsonlAppender(Path(artifacts.path("failures.jsonl", kind=RunArtifactKind.LOG)))
        self.run_id = run_id
        self._sequence = 0
        self._sequence_lock = threading.Lock()

    def _envelope(self, kind: str) -> dict[str, object]:
        with self._sequence_lock:
            self._sequence += 1
            sequence = self._sequence
        return {
            "kind": kind,
            "run_id": self.run_id,
            "diagnostic_sequence": sequence,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def event(
        self,
        event: str = "",
        *,
        phase: str = "workload",
        attributes: Mapping[str, object] | None = None,
        level: str = "DEBUG",
        correlation_refs: tuple[str, ...] = (),
    ) -> None:
        row = self._envelope("event")
        row.update(
            {
                "phase": phase,
                "event": event,
                "level": level,
                "attributes": dict(attributes or {}),
                "correlation_refs": tuple(str(item) for item in correlation_refs),
            }
        )
        self.events.append(row)

    def metric(
        self,
        name: str = "",
        value: float = 0.0,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        row = self._envelope("metric")
        row.update({"name": name, "value": float(value), "labels": dict(labels or {})})
        self.metrics.append(row)

    def failure(
        self,
        code: str = "",
        message: str = "",
        *,
        phase: str = "workload",
        exception: BaseException | None = None,
        attributes: Mapping[str, object] | None = None,
        correlation_refs: tuple[str, ...] = (),
    ) -> None:
        row = self._envelope("failure")
        row.update(
            {
                "phase": phase,
                "code": code,
                "message": message,
                "exception_type": type(exception).__name__ if exception is not None else None,
                "attributes": dict(attributes or {}),
                "correlation_refs": tuple(str(item) for item in correlation_refs),
            }
        )
        if exception is not None:
            row["traceback"] = "".join(traceback.format_exception(exception))
            row["cause_chain"] = exception_chain(exception)
        self.failures.append(row)


__all__ = ["JsonlAppender", "JsonlRunDiagnostics", "exception_chain", "json_default"]
