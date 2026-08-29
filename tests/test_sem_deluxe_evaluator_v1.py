from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from projects.sem_paper.method.self_evolving_memory.evolution import (
    BranchRole,
    CandidateArchitecture,
    CandidateEvaluationError,
    PairedBranchEvaluator,
    PrimitiveEdit,
    PrimitiveEditKind,
)
from research_platform.experimentation.evaluation.api import BranchReceipt


def _candidate() -> CandidateArchitecture:
    return CandidateArchitecture(
        base_generation="g1",
        candidate_id="candidate-1",
        target_spec={"candidate": 1},
        target_spec_digest="d" * 64,
        primitive_edits=(PrimitiveEdit(PrimitiveEditKind.CREATE, "deluxe-node", {}),),
        materialization_contracts=({"node_id": "deluxe-node"},),
    )


def _receipt(branch_id: str, *, workload: str = "workload-1", metrics=(('utility', 1.0),)) -> BranchReceipt:
    return BranchReceipt(
        branch_id=branch_id,
        source_checkpoint_id="checkpoint-1",
        workload_id=workload,
        environment_generation="environment-1",
        task_manifest_digest="tasks-1",
        branch_writes=(),
        lifetime_writes=(),
        private_to_method_flows=(),
        metrics=metrics,
    )


@dataclass
class _Runner:
    control: BranchReceipt
    candidate: BranchReceipt
    calls: list[tuple[BranchRole, CandidateArchitecture | None]]

    def run(self, *, role: BranchRole, candidate: CandidateArchitecture | None) -> BranchReceipt:
        self.calls.append((role, candidate))
        return self.control if role is BranchRole.CONTROL else self.candidate


def test_paired_evaluator_runs_isolated_roles_and_exports_metric_deltas() -> None:
    runner = _Runner(_receipt("control", metrics=(("utility", 0.5),)), _receipt("candidate", metrics=(("utility", 0.8),)), [])
    proof = PairedBranchEvaluator(runner).evaluate(_candidate())

    assert proof.comparability.valid is True
    assert proof.metrics["control.utility"] == 0.5
    assert proof.metrics["candidate.utility"] == 0.8
    assert proof.metrics["delta.utility"] == 0.30000000000000004
    assert runner.calls[0] == (BranchRole.CONTROL, None)
    assert runner.calls[1][0] is BranchRole.CANDIDATE
    assert runner.calls[1][1] is not None


def test_paired_evaluator_preserves_invalid_comparability_as_evidence() -> None:
    runner = _Runner(_receipt("control"), _receipt("candidate", workload="different-workload"), [])
    result = PairedBranchEvaluator(runner).evaluate_with_receipts(_candidate())

    assert result.proof.comparability.valid is False
    assert "workload_id mismatch" in result.proof.comparability.violations
    assert result.proof.metrics["comparability.valid"] == 0.0


def test_paired_evaluator_rejects_reused_branch_identity() -> None:
    runner = _Runner(_receipt("same"), _receipt("same"), [])
    result = PairedBranchEvaluator(runner).evaluate_with_receipts(_candidate())

    assert result.proof.comparability.valid is False
    assert "control and candidate branch ids must differ" in result.proof.comparability.violations


def test_paired_evaluator_attributes_runner_failure_without_fallback() -> None:
    class FailingRunner:
        def run(self, *, role, candidate):
            if role is BranchRole.CONTROL:
                raise OSError("secret transport detail")
            raise AssertionError("candidate branch must not run after control failure")

    with pytest.raises(CandidateEvaluationError) as caught:
        PairedBranchEvaluator(FailingRunner()).evaluate(_candidate())
    assert caught.value.role is BranchRole.CONTROL
    assert "secret transport detail" not in str(caught.value)
    assert caught.value.failure_correlation_refs == ("evaluation-branch:control",)


def test_evaluator_has_no_acceptance_or_adoption_authority() -> None:
    assert not hasattr(PairedBranchEvaluator, "accept")
    assert not hasattr(PairedBranchEvaluator, "adopt")


@pytest.mark.parametrize(
    "metrics",
    (
        [("utility", 1.0)],
        (("utility",),),
        ((1, 1.0),),
        (("utility", True),),
        (("utility", "1.0"),),
    ),
)
def test_paired_evaluator_rejects_malformed_or_coercive_metrics(metrics) -> None:
    runner = _Runner(_receipt("control", metrics=metrics), _receipt("candidate"), [])
    with pytest.raises(CandidateEvaluationError) as caught:
        PairedBranchEvaluator(runner).evaluate(_candidate())
    assert caught.value.role is BranchRole.CONTROL
    assert caught.value.cause_type == "ValueError"


@pytest.mark.parametrize(
    "field,value",
    (
        ("branch_id", ""),
        ("source_checkpoint_id", 1),
        ("branch_writes", ["write"]),
        ("private_to_method_flows", ("",)),
    ),
)
def test_paired_evaluator_rejects_malformed_receipt_contract(field, value) -> None:
    control = replace(_receipt("control"), **{field: value})
    runner = _Runner(control, _receipt("candidate"), [])
    with pytest.raises(CandidateEvaluationError) as caught:
        PairedBranchEvaluator(runner).evaluate(_candidate())
    assert caught.value.role is BranchRole.CONTROL
    assert caught.value.cause_type == "ValueError"


def test_paired_evaluator_rejects_numeric_metric_overflow() -> None:
    runner = _Runner(
        _receipt("control", metrics=(("utility", 10**10000),)),
        _receipt("candidate"),
        [],
    )
    with pytest.raises(CandidateEvaluationError) as caught:
        PairedBranchEvaluator(runner).evaluate(_candidate())
    assert caught.value.role is BranchRole.CONTROL
    assert caught.value.cause_type == "ValueError"
