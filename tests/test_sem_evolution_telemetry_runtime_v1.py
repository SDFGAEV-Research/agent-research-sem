from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from projects.sem_paper.method.self_evolving_memory.session_snapshot_contracts import (
    SCHEMA_VERSION,
)
from research_platform.participant.method.api import (
    MethodServices,
    MethodTaskOutcome,
    RecallRequest,
)
from research_platform.participant.method.runtime import InMemoryMethodObservationSink
from research_platform.platform.kernel import ExecutionContext
from tests_support import build_fixed_memory_method


def _services() -> MethodServices:
    return MethodServices(InMemoryMethodObservationSink())


def _outcome(*, utility: float = 1.0) -> MethodTaskOutcome:
    return MethodTaskOutcome(
        task_id="task-1",
        family="navigation",
        lineage_id="lineage-1",
        success=True,
        utility=utility,
        steps=1,
        memory_queries=1,
    )


def _rehash(snapshot, document):
    raw = json.dumps(
        document,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return replace(
        snapshot,
        opaque_payload=raw,
        payload_sha256=hashlib.sha256(raw).hexdigest(),
    )


def test_query_and_task_facts_roundtrip_in_exact_session_snapshot() -> None:
    method = build_fixed_memory_method()
    session = method.open_session(session_id="session", services=_services())
    task_context = ExecutionContext(
        "run",
        "trace",
        "task-span",
        task_id="task-1",
        operation_id="task-1:complete",
    )
    query_context = replace(
        task_context,
        span_id="query-span",
        decision_cycle_id="task-1:cycle:0",
    )
    session.ingest({"fact": "oak tree"}, task_context)
    recalled = session.recall(RecallRequest("oak tree", query_context, limit=1))
    assert recalled.context_text
    session.task_completed(_outcome(), task_context)

    snapshot = session.checkpoint()
    document = json.loads(snapshot.opaque_payload)
    assert snapshot.schema_version == SCHEMA_VERSION
    assert document["evolution_telemetry"]["queries"][0]["task_id"] == "task-1"
    assert document["evolution_telemetry"]["queries"][0]["opportunity_key"] == "task-1:cycle:0"
    assert document["evolution_telemetry"]["tasks"] == [
        {
            "blocked_by_prior_progress": False,
            "family": "navigation",
            "success": True,
            "task_id": "task-1",
            "utility": 1.0,
        }
    ]

    restored = method.open_session(session_id="session", services=_services())
    restored.restore(snapshot)
    assert json.loads(restored.checkpoint().opaque_payload)["evolution_telemetry"] == document[
        "evolution_telemetry"
    ]


def test_completed_task_retry_rejects_scientific_outcome_drift() -> None:
    session = build_fixed_memory_method().open_session(
        session_id="session",
        services=_services(),
    )
    context = ExecutionContext(
        "run",
        "trace",
        "span",
        task_id="task-1",
        operation_id="task-1:complete",
    )
    session.task_completed(_outcome(), context)
    session.task_completed(_outcome(), context)
    with pytest.raises(ValueError, match="outcome drift"):
        session.task_completed(_outcome(utility=0.5), context)
    assert session.diagnostics()["tasks_completed"] == 1


def test_invalid_telemetry_is_rejected_before_live_state_restore() -> None:
    source = build_fixed_memory_method().open_session(
        session_id="session",
        services=_services(),
    )
    context = ExecutionContext(
        "run",
        "trace",
        "span",
        task_id="task-1",
        decision_cycle_id="task-1:cycle:0",
    )
    source.ingest({"fact": "oak"}, context)
    source.recall(RecallRequest("oak", context, limit=1))
    snapshot = source.checkpoint()
    document = json.loads(snapshot.opaque_payload)
    node_id = next(iter(document["evolution_telemetry"]["node_stats"]))
    document["evolution_telemetry"]["node_stats"][node_id]["avg_result_score"] = 999.0

    target = build_fixed_memory_method().open_session(
        session_id="session",
        services=_services(),
    )
    target.ingest({"live": "unchanged"}, context)
    before = target.diagnostics()
    with pytest.raises(ValueError, match="average score"):
        target.restore(_rehash(snapshot, document))
    after = target.diagnostics()
    assert after["evidence_digest"] == before["evidence_digest"]
    assert after["evidence_sequence"] == before["evidence_sequence"]


def test_unscoped_recall_does_not_create_task_scoped_evolution_evidence() -> None:
    session = build_fixed_memory_method().open_session(
        session_id="session",
        services=_services(),
    )
    context = ExecutionContext("run", "trace", "span")
    session.ingest({"fact": "oak"}, context)
    session.recall(RecallRequest("oak", context, limit=1))
    document = json.loads(session.checkpoint().opaque_payload)
    assert document["evolution_telemetry"]["queries"] == []
