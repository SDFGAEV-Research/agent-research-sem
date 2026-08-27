from __future__ import annotations

from projects.sem_paper.composition.scientific_closure import (
    SemPaperScientificClosureService,
)
from projects.sem_paper.composition.scientific_metrics import (
    ScientificAuxiliaryEvidence,
    SemPaperScientificMetricProvider,
    decode_scientific_auxiliary_evidence,
)
from projects.sem_paper.composition.study import (
    build_sem_paper_study_protocol,
    compile_sem_paper_experiment_plan,
)
from research_platform.experimentation.study.api import (
    StudyMatrixExecutionReport,
    StudyMetricAggregate,
    StudyMetricObservation,
)
from research_platform.experimentation.study.runtime.protocol import (
    DeterministicStudyAssignment,
)


_DIGEST = "a" * 64


def _plan_and_report():
    protocol = build_sem_paper_study_protocol(
        study_id="sem-test",
        workload_id="sem-test-workload",
        task_manifest_digest=_DIGEST,
        seed_identity={"seed": "test"},
        fixed_configuration={},
        candidate_configuration={},
        matrix_profile="core-6",
    )
    plan = compile_sem_paper_experiment_plan(protocol)
    values = {
        "Fixed-C": 1.0,
        "Rule-C": 1.1,
        "Self-C": 1.2,
        "Fixed-X": 2.0,
        "Rule-X": 2.2,
        "Self-X": 2.4,
    }
    observations = tuple(
        StudyMetricObservation(
            assignment,
            (("utility_mean", values[assignment.variant_id]), ("task_blocked_total", 0.0)),
        )
        for assignment in DeterministicStudyAssignment().assignments(protocol)
    )
    aggregates = tuple(
        StudyMetricAggregate(
            protocol.study_id,
            binding.variant.variant_id,
            "utility_mean",
            protocol.repetitions,
            values[binding.variant.variant_id],
            0.0,
            0.0,
        )
        for binding in plan.bindings
    )
    report = StudyMatrixExecutionReport(
        protocol.protocol_digest,
        observations,
        aggregates,
        binding_digest=plan.binding_digest,
        plan_digest=plan.plan_digest,
    )
    return plan, report


def _auxiliary(plan) -> ScientificAuxiliaryEvidence:
    return ScientificAuxiliaryEvidence(
        schema_version="sem-scientific-auxiliary.v2",
        evidence_id="sem-test-auxiliary",
        producer="test-fixture",
        source_tree_digest=_DIGEST,
        plan_digest=plan.plan_digest,
        protocol_digest=plan.protocol_digest,
        binding_digest=plan.binding_digest,
        values=(("ELCE", 0.3), ("GAG", 0.9), ("HPEF", 0.8), ("TDP", 0.1)),
        evidence_refs=("artifact://held-out",),
    )


def test_auxiliary_evidence_is_exact_and_digest_bound() -> None:
    plan, _ = _plan_and_report()
    evidence = _auxiliary(plan)
    decoded = decode_scientific_auxiliary_evidence(
        {
            "schema_version": evidence.schema_version,
            "evidence_id": evidence.evidence_id,
            "producer": evidence.producer,
            "source_tree_digest": evidence.source_tree_digest,
            "plan_digest": evidence.plan_digest,
            "protocol_digest": evidence.protocol_digest,
            "binding_digest": evidence.binding_digest,
            "values": dict(evidence.values),
            "evidence_refs": list(evidence.evidence_refs),
        }
    )
    assert decoded.digest == evidence.digest


def test_core6_statistics_retain_pairwise_arms_and_holm_metadata() -> None:
    plan, report = _plan_and_report()
    provider = SemPaperScientificMetricProvider()
    metrics = provider.compute(plan=plan, report=report, auxiliary_evidence=_auxiliary(plan))
    statistics = provider.compute_statistics(plan=plan, report=report)
    assert metrics.eligible
    assert statistics.eligible
    assert len(statistics.comparisons) == 3
    assert any(item.comparison_id == "SelfEvolve_vs_FixedSeed" for item in statistics.comparisons)
    assert all(item.correction_method == "holm_bonferroni" for item in statistics.comparisons)


def test_closure_blocks_without_live_evidence() -> None:
    plan, report = _plan_and_report()
    result = SemPaperScientificClosureService().evaluate(
        plan=plan,
        report=report,
        source_digest=_DIGEST,
        live_evidence_path=None,
        auxiliary_evidence_path=None,
        mode="baseline",
        model_request_count=1,
        evolution_binding_complete=True,
        evolution_binding_digest=_DIGEST,
        evolution_scientific_ready=True,
    )
    assert not result.gate.eligible
    assert result.live_evidence.claim_eligible is False
    assert "metric:TDP" in result.gate.reasons
    assert any(item.startswith("live_evidence:") for item in result.gate.reasons)
