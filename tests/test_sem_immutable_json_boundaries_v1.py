from __future__ import annotations

import pytest

from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore
from projects.sem_paper.method.self_evolving_memory.evolution.probes import ProbeResult
from projects.sem_paper.method.self_evolving_memory.evolution.telemetry_contracts import (
    IncidentKind,
    MemoryIncident,
    QueryRecordObservation,
)
from projects.sem_paper.method.self_evolving_memory.serving import (
    MemoryServingRecord,
    ServingRuntimeState,
)


def test_jmem_record_deep_snapshots_payload_and_preserves_chain_identity():
    source = {"nested": {"items": [1, 2]}}
    store = InMemoryEvidenceStore()
    row = store.append_payload("e1", 1, source)
    before = store.cut()

    source["nested"]["items"].append(3)
    source["nested"]["extra"] = True

    assert row.payload["nested"]["items"] == [1, 2]
    assert "extra" not in row.payload["nested"]
    assert store.cut() == before
    with pytest.raises(TypeError):
        row.payload["nested"]["new"] = 1


def test_serving_boundaries_deep_snapshot_nested_json():
    record_source = {"nested": {"items": ["a"]}}
    state_source = {"provider": {"cursor": [1, 2]}}
    record = MemoryServingRecord("node", "record", 0.5, record_source, ("e1",))
    state = ServingRuntimeState("kind", "1", state_source)

    record_source["nested"]["items"].append("b")
    state_source["provider"]["cursor"].append(3)

    assert record.payload["nested"]["items"] == ["a"]
    assert state.payload["provider"]["cursor"] == [1, 2]
    with pytest.raises(TypeError):
        record.payload["nested"]["new"] = "x"
    with pytest.raises(TypeError):
        state.payload["provider"]["new"] = 1


def test_telemetry_and_probe_outputs_are_deeply_read_only():
    query_source = {"nested": {"items": [1]}}
    detail_source = {"fields": {"name": ["a", "b"]}}
    facts_source = {"nodes": {"n": {"counts": [1, 2]}}}
    query = QueryRecordObservation("n", "r", 1.0, query_source, ("e1",))
    incident = MemoryIncident(
        "inc", IncidentKind.CONFLICTING_RETRIEVAL, "task", "intent", ("n",), detail_source
    )
    probe = ProbeResult("probe", "PROFILE", facts_source)

    query_source["nested"]["items"].append(2)
    detail_source["fields"]["name"].append("c")
    facts_source["nodes"]["n"]["counts"].append(3)

    assert query.payload["nested"]["items"] == [1]
    assert incident.detail["fields"]["name"] == ["a", "b"]
    assert probe.facts["nodes"]["n"]["counts"] == [1, 2]
    with pytest.raises(TypeError):
        query.payload["nested"]["new"] = 1
    with pytest.raises(TypeError):
        incident.detail["fields"]["new"] = 1
    with pytest.raises(TypeError):
        probe.facts["nodes"]["n"]["new"] = 1


def test_json_boundaries_reject_nonfinite_or_nonjson_values():
    with pytest.raises(ValueError, match="non-finite"):
        ServingRuntimeState("kind", "1", {"bad": float("nan")})
    with pytest.raises(TypeError, match="unsupported type"):
        ProbeResult("probe", "PROFILE", {"bad": object()})
