import math

import pytest

from projects.sem_paper.method.self_evolving_memory.architecture import (
    SemPaperArchitecturePreset,
    build_sem_paper_architecture,
)
from projects.sem_paper.method.self_evolving_memory.evolution import (
    ArchitectureObservationReport,
    CandidateArchitecture,
    EditKind,
    EvaluationProof,
    EvolutionEligibility,
    EvolutionOutcome,
    IncidentKind,
    MemoryIncident,
    NodeObservationProfile,
    NodeRuntimeStats,
    QueryObservation,
    QueryRecordObservation,
    NodePairObservation,
    PrimitiveEdit,
    PrimitiveEditKind,
    StructuralIntent,
    TaskObservation,
    TelemetryBook,
    TelemetryLimits,
    TelemetrySnapshot,
    UnresolvedIntentCluster,
)
from projects.sem_paper.method.self_evolving_memory.evolution.eligibility import (
    EligibilityPolicy,
    ExposureClock,
)
from research_platform.experimentation.evaluation.api import ComparabilityProof


def _proof(*, valid: bool = True) -> ComparabilityProof:
    violations = () if valid else ("mismatch",)
    return ComparabilityProof(valid, "pair", violations, "checkpoint", "workload", "environment", "tasks")


def test_evolution_eligibility_requires_typed_flag_and_reason() -> None:
    with pytest.raises(ValueError, match="boolean"):
        EvolutionEligibility(1, "eligible")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="reason_code"):
        EvolutionEligibility(True, "")


@pytest.mark.parametrize("count", (True, -1, 1.5))
def test_node_pair_rejects_non_integer_or_negative_counts(count: object) -> None:
    with pytest.raises(ValueError, match="co_select_count"):
        NodePairObservation("pair:a:b", "a", "b", count)  # type: ignore[arg-type]


def test_node_pair_requires_distinct_typed_identities() -> None:
    with pytest.raises(ValueError, match="distinct"):
        NodePairObservation("pair:a:a", "a", "a", 1)
    with pytest.raises(ValueError, match="identity"):
        NodePairObservation("pair", 1, "b", 1)  # type: ignore[arg-type]


@pytest.mark.parametrize("support", (True, 0, -1, 1.5))
def test_unresolved_cluster_requires_positive_integer_support(support: object) -> None:
    with pytest.raises(ValueError, match="support"):
        UnresolvedIntentCluster("cluster", support)  # type: ignore[arg-type]


def test_unresolved_cluster_examples_are_bounded_by_support() -> None:
    with pytest.raises(ValueError, match="examples cannot exceed support"):
        UnresolvedIntentCluster("cluster", 1, ("one", "two"))
    with pytest.raises(ValueError, match="examples"):
        UnresolvedIntentCluster("cluster", 1, ["one"])  # type: ignore[arg-type]


def test_architecture_observation_rejects_duplicate_evidence_and_boolean_incident_count() -> None:
    with pytest.raises(ValueError, match="duplicate evidence"):
        ArchitectureObservationReport("g0", "neutral", ("e1", "e1"))
    with pytest.raises(ValueError, match="incident counts"):
        ArchitectureObservationReport("g0", "neutral", (), incident_counts=(("fault", True),))


def test_architecture_observation_rejects_unknown_pair_nodes() -> None:
    architecture = build_sem_paper_architecture(SemPaperArchitecturePreset.C)
    known = architecture.nodes[0].node_id
    report_pair = NodePairObservation("pair:known:missing", known, "missing", 1)
    with pytest.raises(ValueError, match="unknown nodes"):
        ArchitectureObservationReport(
            "g0",
            "neutral",
            (),
            architecture=architecture,
            pairs=(report_pair,),
        )


def test_architecture_observation_requires_typed_nested_values() -> None:
    with pytest.raises(ValueError, match="node profiles"):
        ArchitectureObservationReport("g0", "neutral", (), node_profiles=(object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unresolved clusters"):
        ArchitectureObservationReport("g0", "neutral", (), unresolved_intent_clusters=(object(),))  # type: ignore[arg-type]


def test_structural_intent_and_primitive_edit_require_typed_identity() -> None:
    with pytest.raises(ValueError, match="EditKind"):
        StructuralIntent("CREATE", "reason")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="rationale"):
        StructuralIntent(EditKind.CREATE, "")
    with pytest.raises(ValueError, match="PrimitiveEditKind"):
        PrimitiveEdit("CREATE", "node")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="target"):
        PrimitiveEdit(PrimitiveEditKind.CREATE, "")


def test_candidate_architecture_rejects_weak_container_identity() -> None:
    edit = PrimitiveEdit(PrimitiveEditKind.CREATE, "node")
    with pytest.raises(ValueError, match="base generation"):
        CandidateArchitecture("", "candidate", {}, "digest", (edit,), ())
    with pytest.raises(ValueError, match="primitive edits"):
        CandidateArchitecture("g0", "candidate", {}, "digest", [edit], ())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="materialization contracts"):
        CandidateArchitecture("g0", "candidate", {}, "digest", (edit,), [])  # type: ignore[arg-type]


@pytest.mark.parametrize("metrics", ({"": 1.0}, {"score": True}, {"score": math.inf}, {"score": math.nan}))
def test_evaluation_proof_rejects_invalid_metrics(metrics: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="metric"):
        EvaluationProof(_proof(), metrics)  # type: ignore[arg-type]


def test_evaluation_proof_requires_comparability_proof() -> None:
    with pytest.raises(ValueError, match="ComparabilityProof"):
        EvaluationProof(object(), {"score": 1.0})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "outcome",
    (
        ("unknown", None, None, None, None),
        ("deferred", "g0", None, None, "wait"),
        ("deferred", None, None, None, None),
        ("no_edit", "g0", "g1", EditKind.NO_EDIT, None),
        ("no_edit", "g0", "g0", EditKind.CREATE, None),
        ("invalid_evaluation", "g0", "g0", EditKind.CREATE, None),
        ("invalid_evaluation", "g0", "g1", EditKind.CREATE, "mismatch"),
        ("rejected", "g0", "g1", EditKind.CREATE, None),
        ("rejected", "g0", "g0", EditKind.NO_EDIT, None),
        ("adopted", "g0", "g0", EditKind.CREATE, None),
        ("adopted", "g0", "g1", EditKind.NO_EDIT, None),
        ("adopted", "g0", "g1", EditKind.CREATE, "reason"),
    ),
)
def test_evolution_outcome_rejects_inconsistent_state_matrix(outcome: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        EvolutionOutcome(*outcome)  # type: ignore[arg-type]


def test_evolution_outcome_accepts_every_canonical_pipeline_state() -> None:
    values = (
        EvolutionOutcome("deferred", None, None, None, "minimum_dwell"),
        EvolutionOutcome("no_edit", "g0", "g0", EditKind.NO_EDIT),
        EvolutionOutcome("invalid_evaluation", "g0", "g0", EditKind.CREATE, "mismatch"),
        EvolutionOutcome("rejected", "g0", "g0", EditKind.CREATE),
        EvolutionOutcome("adopted", "g0", "g1", EditKind.CREATE),
    )
    assert tuple(item.status for item in values) == (
        "deferred",
        "no_edit",
        "invalid_evaluation",
        "rejected",
        "adopted",
    )


@pytest.mark.parametrize(
    "factory,args",
    (
        (ExposureClock, (True, 1, 1, 1)),
        (ExposureClock, (1, -1, 1, 1)),
        (EligibilityPolicy, (True, 1, 1, 1)),
        (EligibilityPolicy, (1, 1, -1, 1)),
    ),
)
def test_eligibility_value_objects_reject_boolean_or_negative_counters(factory, args) -> None:
    with pytest.raises(ValueError):
        factory(*args)


def test_eligibility_value_objects_require_boolean_flags() -> None:
    with pytest.raises(ValueError, match="workload_shift"):
        ExposureClock(1, 1, 1, 1, workload_shift=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="require_workload_shift"):
        EligibilityPolicy(require_workload_shift=1)  # type: ignore[arg-type]


def test_node_observation_profile_rejects_non_string_identity() -> None:
    with pytest.raises(ValueError, match="node id"):
        NodeObservationProfile(1)  # type: ignore[arg-type]


def test_evaluation_proof_snapshots_and_freezes_metrics() -> None:
    source = {"score": 1}
    proof = EvaluationProof(_proof(), source)
    source["score"] = 9

    assert proof.metrics["score"] == 1.0
    assert dict(proof.metrics) == {"score": 1.0}
    with pytest.raises(TypeError):
        proof.metrics["score"] = 2.0  # type: ignore[index]


def test_evaluation_proof_rejects_numeric_overflow_as_value_error() -> None:
    with pytest.raises(ValueError, match="finite"):
        EvaluationProof(_proof(), {"score": 10**10000})


def test_query_record_observation_rejects_coercive_identity_and_score() -> None:
    with pytest.raises(ValueError, match="node id"):
        QueryRecordObservation(1, "record", 1.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="numeric"):
        QueryRecordObservation("node", "record", "1.0")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="numeric"):
        QueryRecordObservation("node", "record", True)  # type: ignore[arg-type]


def test_query_record_observation_snapshots_payload_mapping() -> None:
    payload = {"value": "oak"}
    observation = QueryRecordObservation("node", "record", 1, payload)
    payload["value"] = "birch"
    assert observation.score == 1.0
    assert observation.payload["value"] == "oak"
    with pytest.raises(TypeError):
        observation.payload["value"] = "spruce"  # type: ignore[index]


def test_node_runtime_stats_rejects_bool_and_text_numeric_state() -> None:
    with pytest.raises(ValueError, match="counts"):
        NodeRuntimeStats(selected_count=True)
    with pytest.raises(ValueError, match="numeric"):
        NodeRuntimeStats(score_sum="1.0")  # type: ignore[arg-type]


def test_query_and_task_observations_reject_coercive_scalars() -> None:
    with pytest.raises(ValueError, match="record_count"):
        QueryObservation("q", "task", "intent", None, (), (), (), 0.0, True, 0)
    with pytest.raises(ValueError, match="top_score"):
        QueryObservation("q", "task", "intent", None, (), (), (), "0.0", 0, 0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="utility"):
        TaskObservation("task", "family", True, "1.0")  # type: ignore[arg-type]


def test_memory_incident_snapshots_top_level_detail() -> None:
    detail = {"reason": "miss"}
    incident = MemoryIncident("inc", IncidentKind.RETRIEVAL_MISS, "task", "intent", ("node",), detail)
    detail["reason"] = "rewritten"
    assert incident.detail["reason"] == "miss"
    with pytest.raises(TypeError):
        incident.detail["reason"] = "other"  # type: ignore[index]


def test_memory_incident_rejects_duplicate_or_untyped_node_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        MemoryIncident("inc", IncidentKind.RETRIEVAL_MISS, "task", "intent", ("node", "node"), {})
    with pytest.raises(ValueError, match="node ids"):
        MemoryIncident("inc", IncidentKind.RETRIEVAL_MISS, "task", "intent", (1,), {})  # type: ignore[arg-type]


def test_telemetry_snapshot_canonicalizes_and_freezes_node_stats() -> None:
    row = NodeRuntimeStats(result_count=2, score_sum=1).as_dict()
    source = {"node": row}
    snapshot = TelemetrySnapshot(source, (), (), ())
    row["result_count"] = 99
    source["other"] = NodeRuntimeStats().as_dict()
    assert snapshot.node_stats["node"]["result_count"] == 2
    assert snapshot.node_stats["node"]["score_sum"] == 1.0
    assert "other" not in snapshot.node_stats
    with pytest.raises(TypeError):
        snapshot.node_stats["node"]["result_count"] = 3  # type: ignore[index]


def test_telemetry_snapshot_rejects_bool_cursor_and_untyped_rows() -> None:
    with pytest.raises(ValueError, match="cursor"):
        TelemetrySnapshot({}, (), (), (), block_query_cursor=True)
    with pytest.raises(ValueError, match="typed tuple"):
        TelemetrySnapshot({}, [], (), ())  # type: ignore[arg-type]


def test_telemetry_book_rejects_coercive_query_inputs() -> None:
    book = TelemetryBook()
    with pytest.raises(ValueError, match="selected node ids"):
        book.record_query(task_id="task", intent="intent", opportunity_key=None, selected_nodes=(1,), records=())
    with pytest.raises(ValueError, match="min_useful_score"):
        book.record_query(task_id="task", intent="intent", opportunity_key=None, selected_nodes=(), records=(), min_useful_score="0.1")  # type: ignore[arg-type]


def test_telemetry_book_requires_typed_records_and_task_observations() -> None:
    book = TelemetryBook()
    with pytest.raises(ValueError, match="typed query record"):
        book.record_query(task_id="task", intent="intent", opportunity_key=None, selected_nodes=(), records=(object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_reasonable_nodes"):
        book.record_query(task_id="task", intent="intent", opportunity_key=None, selected_nodes=(), records=(), max_reasonable_nodes=True)
    with pytest.raises(TypeError, match="task observation"):
        book.record_task(object())  # type: ignore[arg-type]


def test_telemetry_book_constructor_rejects_untyped_state() -> None:
    with pytest.raises(TypeError, match="limits"):
        TelemetryBook(limits=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="node state"):
        TelemetryBook(node_stats={1: NodeRuntimeStats()})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="queries state"):
        TelemetryBook(queries=[object()])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="cursor"):
        TelemetryBook(_block_query_cursor=True)


def test_telemetry_book_constructor_rejects_duplicate_typed_ids() -> None:
    task = TaskObservation("task", "family", True, 1.0)
    with pytest.raises(ValueError, match="duplicate ids"):
        TelemetryBook(tasks=[task, task], limits=TelemetryLimits(max_tasks=2))
