from __future__ import annotations

import pytest

from projects.sem_paper.method.self_evolving_memory.evolution.telemetry import (
    TaskObservation,
    TelemetryBook,
    TelemetryCapacityExceeded,
    TelemetryLimits,
)


def _query(book: TelemetryBook, task_id: str, node_id: str = "events", *, opportunity: bool = False) -> None:
    book.record_query(
        task_id=task_id,
        intent="find resource",
        opportunity_key=f"op-{task_id}" if opportunity else None,
        selected_nodes=(node_id,),
        records=(),
    )


def test_capacity_query_incident_preflight_is_atomic() -> None:
    book = TelemetryBook(limits=TelemetryLimits(max_nodes=2, max_queries=2, max_incidents=1, max_tasks=2))
    with pytest.raises(TelemetryCapacityExceeded, match="incident capacity"):
        _query(book, "task-1", opportunity=True)
    assert book.queries == []
    assert book.incidents == []
    assert book.node_stats == {}


def test_capacity_query_and_node_limits_fail_closed_without_partial_state() -> None:
    book = TelemetryBook(limits=TelemetryLimits(max_nodes=1, max_queries=2, max_incidents=4, max_tasks=2))
    _query(book, "task-1", "events")
    before = book.snapshot()
    with pytest.raises(TelemetryCapacityExceeded, match="node capacity"):
        _query(book, "task-2", "facts")
    assert book.snapshot() == before

    full = TelemetryBook(limits=TelemetryLimits(max_nodes=1, max_queries=1, max_incidents=4, max_tasks=2))
    _query(full, "task-1")
    before = full.snapshot()
    with pytest.raises(TelemetryCapacityExceeded, match="query capacity"):
        _query(full, "task-2")
    assert full.snapshot() == before


def test_capacity_task_index_preserves_idempotency_at_limit() -> None:
    book = TelemetryBook(limits=TelemetryLimits(max_nodes=1, max_queries=1, max_incidents=1, max_tasks=1))
    observation = TaskObservation("task-1", "collect", True, 1.0)
    book.record_task(observation)
    book.record_task(observation)
    assert book.tasks == [observation]
    with pytest.raises(ValueError, match="outcome drift"):
        book.record_task(TaskObservation("task-1", "collect", False, 0.0))
    with pytest.raises(TelemetryCapacityExceeded, match="task capacity"):
        book.record_task(TaskObservation("task-2", "collect", True, 1.0))
    assert book.tasks == [observation]


def test_capacity_restore_rejects_oversized_snapshot_without_mutation() -> None:
    source = TelemetryBook(limits=TelemetryLimits(max_nodes=2, max_queries=2, max_incidents=4, max_tasks=2))
    _query(source, "task-1")
    _query(source, "task-2")
    snapshot = source.snapshot()

    target = TelemetryBook(limits=TelemetryLimits(max_nodes=2, max_queries=1, max_incidents=4, max_tasks=2))
    before = target.snapshot()
    with pytest.raises(TelemetryCapacityExceeded, match="query capacity exceeded by snapshot"):
        target.restore(snapshot)
    assert target.snapshot() == before
