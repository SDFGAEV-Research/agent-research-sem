from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.record.api import LogLevel, LogRecord
from research_platform.observability.logging.storage.runtime.jsonl import JsonlLogCorruptionError
from tests._concurrency_support import jsonl_log_store as JsonlLogStore
from research_platform.observability.logging.storage.composition import build_jsonl_log_store
from research_platform.platform.concurrency.composition import build_concurrency_runtime
from research_platform.scope.api import PLATFORM_SCOPE


def _record(index: int) -> LogRecord:
    return LogRecord(
        f"log-{index}",
        float(index),
        LogLevel.INFO,
        "test",
        "event",
        "safe",
        DiagnosticAddress((PLATFORM_SCOPE,)),
    )


def test_query_limit_returns_globally_newest_records_without_rotation(tmp_path: Path) -> None:
    store = JsonlLogStore(tmp_path / "events.jsonl")
    for index in range(5):
        store.append(_record(index))
    assert [row.log_id for row in store.query(limit=3)] == ["log-4", "log-3", "log-2"]


def test_query_limit_returns_globally_newest_records_across_segments(tmp_path: Path) -> None:
    store = JsonlLogStore(tmp_path / "events.jsonl", max_bytes=1, max_segments=4)
    for index in range(5):
        store.append(_record(index))
    assert [row.log_id for row in store.query(limit=3)] == ["log-4", "log-3", "log-2"]
    assert (tmp_path / "events.jsonl.4").exists()


def test_wrong_schema_is_corruption_not_silently_decoded(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    store = JsonlLogStore(path)
    store.append(_record(1))
    row = json.loads(path.read_text(encoding="utf-8"))
    row["schema_version"] = "wrong.schema"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(JsonlLogCorruptionError):
        store.query()


def _append_worker(path: str, worker: int, count: int) -> None:
    runtime = build_concurrency_runtime()
    group = runtime.open_task_group(f"multiprocess-log-writer:{worker}")
    store = build_jsonl_log_store(path, task_group=group, max_bytes=700, max_segments=64)
    try:
        for offset in range(count):
            index = worker * 1000 + offset
            store.append(_record(index))
    finally:
        runtime.close()


def test_multiple_processes_append_and_rotate_without_overwrite(tmp_path: Path) -> None:
    import multiprocessing

    path = tmp_path / "events.jsonl"
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=_append_worker, args=(str(path), worker, 12)) for worker in range(4)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
        assert process.exitcode == 0
    rows = JsonlLogStore(path, max_bytes=700, max_segments=64).query(limit=1000)
    assert len(rows) == 48
    assert len({row.log_id for row in rows}) == 48
