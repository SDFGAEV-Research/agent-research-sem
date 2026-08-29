from __future__ import annotations

import json
from dataclasses import replace

import pytest

from research_platform.platform.kernel import ExecutionContext, canonical_bytes
from research_platform.participant.method.api import MethodObservationDeliveryError, MethodServices, RecallRequest
from research_platform.participant.method.runtime import InMemoryMethodObservationSink
from sem_test_support import build_fixed_memory_method


def _rich_checkpoint():
    method = build_fixed_memory_method()
    session = method.open_session(
        session_id="s",
        services=MethodServices(InMemoryMethodObservationSink()),
    )
    context = ExecutionContext("run", "trace", "span", task_id="task", decision_cycle_id="dc")
    session.ingest({"x": 1}, context)
    session.recall(RecallRequest("x", context, 1))
    session.task_completed({}, context)
    return method, session.checkpoint()


def _resign(snapshot, mutate):
    document = json.loads(snapshot.opaque_payload)
    mutate(document)
    raw = canonical_bytes(document)
    return replace(snapshot, opaque_payload=raw, payload_sha256=__import__("hashlib").sha256(raw).hexdigest())


def _set_path(document, path, value):
    current = document
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "value", "message"),
    (
        (("state", "evidence_sequence"), True, "integer"),
        (("evidence", "rows", 0, "sequence"), True, "integer"),
        (("lineage", "revision"), True, "integer"),
        (("lineage", "mutation_tail", 0, "before_closed"), 0, "boolean"),
        (("task_progress", 0, "task_key"), 123, "non-empty string"),
        (("evolution_telemetry", "queries", 0, "record_count"), True, "integer"),
        (("evolution_telemetry", "queries", 0, "selected_nodes", 0), 7, "non-empty string"),
        (("serving_state", "state_kind"), 7, "non-empty string"),
    ),
)
def test_nested_snapshot_types_are_not_silently_coerced(path, value, message) -> None:
    method, snapshot = _rich_checkpoint()
    malformed = _resign(snapshot, lambda document: _set_path(document, path, value))
    target = method.open_session(
        session_id="s",
        services=MethodServices(InMemoryMethodObservationSink()),
    )

    with pytest.raises(ValueError, match=message):
        target.restore(malformed)

    assert target.diagnostics()["restore_fault"] is None
    target.ingest({"still": "usable"}, ExecutionContext("run2", "trace2", "span2"))
    assert target.diagnostics()["evidence_sequence"] == 1


def test_nested_snapshot_objects_require_exact_fields() -> None:
    method, snapshot = _rich_checkpoint()
    malformed = _resign(snapshot, lambda document: document["state"].__setitem__("unexpected", 1))
    target = method.open_session(
        session_id="s",
        services=MethodServices(InMemoryMethodObservationSink()),
    )

    with pytest.raises(ValueError, match="fields are not exact"):
        target.restore(malformed)

    assert target.diagnostics()["restore_fault"] is None
    assert target.diagnostics()["evidence_sequence"] == 0


def test_resigned_corrupt_jmem_fails_during_prepare_before_any_restore_owner_moves() -> None:
    method, snapshot = _rich_checkpoint()

    def corrupt(document):
        document["evidence"]["rows"][0]["payload"] = {"x": 999}

    malformed = _resign(snapshot, corrupt)
    target = method.open_session(
        session_id="s",
        services=MethodServices(InMemoryMethodObservationSink()),
    )
    before = target.checkpoint()

    with pytest.raises(ValueError, match="J_mem evidence digest mismatch"):
        target.restore(malformed)

    assert target.diagnostics()["restore_fault"] is None
    assert target.checkpoint().opaque_payload == before.opaque_payload


def test_pending_observation_context_identity_is_strictly_typed() -> None:
    class Down:
        def record(self, observation):
            raise OSError("down")

    method = build_fixed_memory_method()
    source = method.open_session(session_id="pending", services=MethodServices(Down()))
    with pytest.raises(MethodObservationDeliveryError):
        source.ingest({"x": 1}, ExecutionContext("run", "trace", "span"))
    snapshot = source.checkpoint()

    def corrupt(document):
        assert document["pending_observations"]
        document["pending_observations"][0]["context"]["run_id"] = 17

    malformed = _resign(snapshot, corrupt)
    target = method.open_session(
        session_id="pending",
        services=MethodServices(InMemoryMethodObservationSink()),
    )
    with pytest.raises(ValueError, match="context run_id"):
        target.restore(malformed)
    assert target.diagnostics()["restore_fault"] is None
