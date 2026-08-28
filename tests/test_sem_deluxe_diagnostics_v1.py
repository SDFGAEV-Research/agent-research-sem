from __future__ import annotations

from dataclasses import replace

from projects.sem_paper.method.self_evolving_memory.architecture import (
    AccessMode,
    FieldSpec,
    MemoryArchitectureSpec,
    MemoryMode,
    MemoryNodeSpec,
    MemoryScope,
    OperatorKind,
    PrimitiveType,
    SourceKind,
    SourceSpec,
    TransformOpSpec,
    TransformPlan,
    TypeSpec,
)
from projects.sem_paper.method.self_evolving_memory.evolution import (
    AdaptiveSlowClock,
    AdoptionObservation,
    AutomaticSliceDiscovery,
    HypothesisRegistry,
    IncidentKind,
    StructuralNodeProbeRequest,
    QueryRecordObservation,
    StructuralProbeEngine,
    TaskObservation,
    TelemetryBook,
)


def _architecture(generation: int = 2) -> MemoryArchitectureSpec:
    return MemoryArchitectureSpec(
        "1",
        "diagnostics",
        generation,
        (
            MemoryNodeSpec(
                "events",
                "Events",
                "grounded events",
                MemoryScope.AGENT,
                MemoryMode.APPEND,
                (FieldSpec("event", TypeSpec(PrimitiveType.TEXT)),),
                (),
                frozenset({AccessMode.SEMANTIC}),
                (SourceSpec(SourceKind.EVIDENCE),),
                TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_MAP),)),
            ),
            MemoryNodeSpec(
                "summary",
                "Summary",
                "derived events",
                MemoryScope.AGENT,
                MemoryMode.AGGREGATE,
                (FieldSpec("statement", TypeSpec(PrimitiveType.TEXT)),),
                ("statement",),
                frozenset({AccessMode.SEMANTIC}),
                (SourceSpec(SourceKind.NODE, node_id="events"),),
                TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_REDUCE),)),
            ),
        ),
    )


def _record(node_id: str, record_id: str, score: float, value: str) -> QueryRecordObservation:
    return QueryRecordObservation(
        node_id=node_id,
        record_id=record_id,
        score=score,
        payload={"value": value},
        source_refs=(f"evidence:{record_id}",),
    )


def test_telemetry_is_explicit_and_neutral() -> None:
    telemetry = TelemetryBook()
    telemetry.record_query(
        task_id="task-1",
        intent="find tree resource",
        opportunity_key="op-1",
        selected_nodes=("events", "summary"),
        records=(
            _record("events", "r1", 0.01, "oak"),
            _record("events", "r2", 0.02, "birch"),
            _record("events", "r3", 0.03, "spruce"),
        ),
        max_reasonable_nodes=1,
    )
    telemetry.record_task(TaskObservation("task-1", "collect", False, 0.0))

    snapshot = telemetry.snapshot()
    assert snapshot.queries[0].record_count == 3
    assert snapshot.node_stats["events"]["result_count"] == 3
    assert {incident.kind for incident in snapshot.incidents} == {
        IncidentKind.UNRESOLVED_MEMORY_INTENT,
        IncidentKind.EXCESSIVE_RETRIEVAL_COST,
        IncidentKind.CONFLICTING_RETRIEVAL,
    }
    assert not hasattr(telemetry, "adopt")
    assert not hasattr(telemetry, "accept")


def test_slices_probes_hypotheses_and_slow_clock_are_rebuildable() -> None:
    telemetry = TelemetryBook()
    telemetry.record_query(
        task_id="task-1",
        intent="find tree resource",
        opportunity_key="op-1",
        selected_nodes=("events",),
        records=(),
    )
    telemetry.record_query(
        task_id="task-2",
        intent="find tree resource",
        opportunity_key="op-2",
        selected_nodes=("events",),
        records=(),
    )
    telemetry.record_node_update("events", records_added=2, full_recompute=True)
    telemetry.record_task(TaskObservation("task-2", "collect", True, 1.0))
    architecture = _architecture()
    store = {"events": (_record("events", "r1", 0.5, "oak"),)}

    slices = AutomaticSliceDiscovery().discover(telemetry.incidents)
    # Each opportunity records both the retrieval miss and its unresolved
    # intent consequence; the diagnostic plane must not collapse those facts.
    assert slices and slices[0].support == 4
    probe = StructuralProbeEngine(architecture, store, telemetry).execute(
        StructuralNodeProbeRequest(("events",))
    )
    assert probe.facts["nodes"]["events"]["record_count"] == 1
    assert probe.facts["nodes"]["events"]["sampled_record_count"] == 1

    hypothesis = HypothesisRegistry().add(
        observation_report_id="aor-1",
        text="event retrieval is unresolved",
        evidence_refs=(slices[0].slice_id,),
    )
    assert hypothesis.evidence_refs == (slices[0].slice_id,)

    clock = AdaptiveSlowClock()
    allowed, facts = clock.allow_review(
        architecture=architecture,
        telemetry=telemetry,
        recent_adoptions=(AdoptionObservation(1, True),),
        episodes_since_activation=10,
    )
    assert allowed is True
    assert facts["node_horizons"]


def test_diagnostic_modules_have_no_legacy_runtime_imports() -> None:
    import inspect
    from projects.sem_paper.method.self_evolving_memory.evolution import (
        hypotheses, pacing, probes, slicing, telemetry
    )

    source = "\n".join(inspect.getsource(module) for module in (telemetry, slicing, probes, hypotheses, pacing))
    assert "memory_ir" not in source
    assert "memory_runtime" not in source
    assert "v034_work" not in source
