from __future__ import annotations

from types import SimpleNamespace

from research_platform.experimentation.evaluation.api import ComparabilityProof
from projects.sem_paper.composition.evolution_production import (
    QualifiedMetaProposalAuthority,
    QualifiedMetaProposalError,
)
from projects.sem_paper.composition.evolution import (
    _EvidenceAcceptance,
    _EvidenceDiagnosis,
    _ReflectionEligibility,
    _RuleBasedEligibility,
)
from projects.sem_paper.method.self_evolving_memory.evolution import (
    ArchitectureObservationReport,
    EditKind,
    EvaluationProof,
    EvolutionPipeline,
    StructuralIntent,
)


class _Source:
    def __init__(self, snapshot) -> None:
        self.current = snapshot

    def snapshot(self):
        return self.current


def _snapshot(*, sequence: int = 1, completed: int = 1, tasks=()):
    telemetry = SimpleNamespace(tasks=tuple(tasks), node_stats={}, queries=(), incidents=())
    return SimpleNamespace(
        generation="g0", evidence_sequence=sequence, evidence_digest=f"evidence-{sequence}",
        tasks_completed=completed, evolution_epoch=0, telemetry=telemetry,
    )


def _proof(*, valid: bool = True, metrics=None) -> EvaluationProof:
    violations = () if valid else ("branch_mismatch",)
    comparison = ComparabilityProof(
        valid, "pair", violations, "checkpoint", "workload", "environment", "tasks"
    )
    return EvaluationProof(comparison, metrics or {})


def _metrics(**overrides: float) -> dict[str, float]:
    values = {
        "control.success_rate": 0.8, "candidate.success_rate": 0.8,
        "control.utility_mean": 0.5, "candidate.utility_mean": 0.5,
        "control.task_blocked_total": 2, "candidate.task_blocked_total": 2,
        "control.task_failed_total": 1, "candidate.task_failed_total": 1,
    }
    values.update(overrides)
    return values


def _intent() -> StructuralIntent:
    return StructuralIntent(EditKind.CREATE, "grounded change", {"evidence_refs": ("e1",)})


def test_first_fresh_evidence_reaches_meta_without_dwell_or_persistence() -> None:
    gate = _ReflectionEligibility(_Source(_snapshot(sequence=1, completed=1, tasks=())))
    result = gate.check()
    assert result.eligible is True
    assert result.reason_code == "fresh_evidence_reflection"


def test_duplicate_evidence_cut_cannot_reflect_twice() -> None:
    source = _Source(_snapshot(sequence=4, completed=1))
    gate = _ReflectionEligibility(source)
    assert gate.check().eligible is True
    second = gate.check()
    assert second.eligible is False
    assert second.reason_code == "evidence_already_reflected"


def test_rule_based_comparator_keeps_dwell_and_persistence_thresholds() -> None:
    task = SimpleNamespace(blocked_by_prior_progress=True)
    gate = _RuleBasedEligibility(_Source(_snapshot(sequence=2, completed=2, tasks=(task, task))))
    assert gate.check().reason_code == "minimum_dwell"


class _NoEditSynthesis:
    def propose(self, report):
        return StructuralIntent(EditKind.NO_EDIT, "maintain", {"evidence_refs": report.evidence_refs})


class _FailIfCalled:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected side effect: {name}")


class _Diagnosis:
    def diagnose(self):
        return ArchitectureObservationReport("g0", "neutral", ("e1",))


def test_meta_no_edit_performs_no_compile_evaluate_or_adopt() -> None:
    pipeline = EvolutionPipeline(
        eligibility=_ReflectionEligibility(_Source(_snapshot())), diagnosis=_Diagnosis(),
        synthesis=_NoEditSynthesis(), compiler=_FailIfCalled(), evaluator=_FailIfCalled(),
        acceptance=_EvidenceAcceptance(), adoption=_FailIfCalled(),
    )
    outcome = pipeline.run()
    assert outcome.status == "no_edit"
    assert outcome.edit is EditKind.NO_EDIT


def test_comparable_candidate_with_lower_success_is_rejected() -> None:
    proof = _proof(metrics=_metrics(**{"candidate.success_rate": 0.7, "candidate.steps_total": 10, "control.steps_total": 20}))
    assert _EvidenceAcceptance().accept(_intent(), proof) is False


def test_comparable_candidate_with_lower_utility_is_rejected() -> None:
    proof = _proof(metrics=_metrics(**{"candidate.utility_mean": 0.4, "candidate.task_failed_total": 0}))
    assert _EvidenceAcceptance().accept(_intent(), proof) is False


def test_fewer_steps_cannot_compensate_for_worse_success() -> None:
    proof = _proof(metrics=_metrics(**{
        "candidate.success_rate": 0.79, "control.steps_total": 100, "candidate.steps_total": 1,
    }))
    assert _EvidenceAcceptance().accept(_intent(), proof) is False


def test_noninferior_candidate_with_strict_benefit_is_accepted() -> None:
    proof = _proof(metrics=_metrics(**{"candidate.task_failed_total": 0}))
    assert _EvidenceAcceptance().accept(_intent(), proof) is True


def test_exact_tie_is_rejected_as_no_demonstrated_benefit() -> None:
    assert _EvidenceAcceptance().accept(_intent(), _proof(metrics=_metrics())) is False


def test_invalid_comparability_is_rejected_before_metric_policy() -> None:
    proof = _proof(valid=False, metrics=_metrics(**{"candidate.success_rate": 1.0}))
    assert _EvidenceAcceptance().accept(_intent(), proof) is False


def test_meta_cannot_cite_evidence_outside_frozen_report() -> None:
    report = ArchitectureObservationReport("g0", "neutral", ("allowed",))
    payload = {"edit": "NO_EDIT", "rationale": "maintain", "evidence_refs": ["future"]}
    try:
        QualifiedMetaProposalAuthority._to_intent(payload, report)
    except QualifiedMetaProposalError as exc:
        assert exc.phase == "authority"
    else:
        raise AssertionError("Meta accepted evidence outside the frozen report")


class _EditSynthesis:
    def propose(self, report):
        return StructuralIntent(EditKind.CREATE, "grounded", {"evidence_refs": report.evidence_refs})


class _Compiler:
    def compile(self, intent, generation):
        return SimpleNamespace(intent=intent, base_generation=generation)


class _Evaluator:
    def __init__(self, proof): self.proof, self.calls = proof, 0
    def evaluate(self, candidate):
        self.calls += 1
        return self.proof


class _Adoption:
    def __init__(self): self.calls = 0
    def adopt(self, candidate, proof, context=None):
        self.calls += 1
        return "g1"


def test_grounded_meta_edit_reaches_evaluation_and_adoption() -> None:
    evaluator = _Evaluator(_proof(metrics=_metrics(**{"candidate.task_failed_total": 0})))
    adoption = _Adoption()
    pipeline = EvolutionPipeline(
        eligibility=_ReflectionEligibility(_Source(_snapshot())), diagnosis=_Diagnosis(),
        synthesis=_EditSynthesis(), compiler=_Compiler(), evaluator=evaluator,
        acceptance=_EvidenceAcceptance(), adoption=adoption,
    )
    outcome = pipeline.run()
    assert outcome.status == "adopted"
    assert evaluator.calls == 1
    assert adoption.calls == 1


def test_invalid_comparability_stops_before_acceptance_and_adoption() -> None:
    evaluator = _Evaluator(_proof(valid=False, metrics=_metrics()))
    adoption = _Adoption()
    pipeline = EvolutionPipeline(
        eligibility=_ReflectionEligibility(_Source(_snapshot())), diagnosis=_Diagnosis(),
        synthesis=_EditSynthesis(), compiler=_Compiler(), evaluator=evaluator,
        acceptance=_FailIfCalled(), adoption=adoption,
    )
    outcome = pipeline.run()
    assert outcome.status == "invalid_evaluation"
    assert evaluator.calls == 1
    assert adoption.calls == 0
