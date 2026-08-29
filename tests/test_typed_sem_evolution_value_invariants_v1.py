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
    NodeObservationProfile,
    NodePairObservation,
    PrimitiveEdit,
    PrimitiveEditKind,
    StructuralIntent,
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
