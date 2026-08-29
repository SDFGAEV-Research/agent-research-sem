from __future__ import annotations

import pytest

import projects.sem_paper.method.self_evolving_memory.evolution as evolution
from projects.sem_paper.method.self_evolving_memory.evolution.probes import (
    IncidentExamplesProbeRequest,
    IntentClusterProbeRequest,
    PairStatsProbeRequest,
    ProfileProbeRequest,
    StructuralNodeProbeRequest,
    StructuralProbeEngine,
)
from projects.sem_paper.method.self_evolving_memory.evolution.telemetry import IncidentKind, TelemetryBook


def test_typed_probe_requests_validate_their_own_shape() -> None:
    assert ProfileProbeRequest("events").kind == "PROFILE"
    assert IncidentExamplesProbeRequest("events", IncidentKind.RETRIEVAL_MISS).kind == "GET_INCIDENT_EXAMPLES"
    assert PairStatsProbeRequest("events", "summary").kind == "GET_PAIR_STATS"
    assert IntentClusterProbeRequest("slice-1").kind == "GET_INTENT_CLUSTER"
    assert StructuralNodeProbeRequest(("events", "summary")).kind == "REQUEST_STRUCTURAL_PROBE"

    with pytest.raises(ValueError, match="one to four"):
        StructuralNodeProbeRequest(())
    with pytest.raises(ValueError, match="one to four"):
        StructuralNodeProbeRequest(("a", "b", "c", "d", "e"))
    with pytest.raises(ValueError, match="unique"):
        StructuralNodeProbeRequest(("events", "events"))
    with pytest.raises(ValueError, match="distinct"):
        PairStatsProbeRequest("events", "events")
    with pytest.raises(ValueError, match="cannot be empty"):
        IncidentExamplesProbeRequest("")


def test_probe_engine_rejects_untyped_mapping_commands() -> None:
    engine = StructuralProbeEngine(object(), {}, TelemetryBook())
    with pytest.raises(TypeError, match="typed request"):
        engine.execute({"kind": "PROFILE", "args": {"node_id": "events"}})  # type: ignore[arg-type]


def test_legacy_generic_probe_spec_is_removed() -> None:
    assert not hasattr(evolution, "ProbeSpec")


@pytest.mark.parametrize(
    "factory",
    (
        lambda: ProfileProbeRequest(7),  # type: ignore[arg-type]
        lambda: IncidentExamplesProbeRequest(7),  # type: ignore[arg-type]
        lambda: IncidentExamplesProbeRequest("events", "RETRIEVAL_MISS"),  # type: ignore[arg-type]
        lambda: PairStatsProbeRequest("events", 7),  # type: ignore[arg-type]
        lambda: IntentClusterProbeRequest(7),  # type: ignore[arg-type]
        lambda: StructuralNodeProbeRequest(["events"]),  # type: ignore[arg-type]
        lambda: StructuralNodeProbeRequest(("events", 7)),  # type: ignore[arg-type]
    ),
)
def test_typed_probe_requests_reject_runtime_type_corruption(factory) -> None:
    with pytest.raises(ValueError):
        factory()
