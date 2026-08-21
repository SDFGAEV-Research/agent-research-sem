from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Protocol

from research_platform.experimentation.evaluation.api import BranchReceipt, build_comparability_proof

from .contracts import CandidateArchitecture, EvaluationProof


class BranchRole(StrEnum):
    CONTROL = "control"
    CANDIDATE = "candidate"


class CandidateEvaluationError(RuntimeError):
    """A branch runner failed; the pipeline remains the stage authority."""

    def __init__(self, role: BranchRole, cause: BaseException) -> None:
        super().__init__(f"SEM candidate evaluation branch failed: {role.value}")
        self.role = role
        self.cause = cause
        self.cause_type = type(cause).__name__

    @property
    def failure_correlation_refs(self) -> tuple[str, ...]:
        return (f"evaluation-branch:{self.role.value}",)


class BranchRunnerPort(Protocol):
    """Project composition seam for one isolated control/candidate branch."""

    def run(
        self,
        *,
        role: BranchRole,
        candidate: CandidateArchitecture | None,
    ) -> BranchReceipt: ...


@dataclass(frozen=True, slots=True)
class PairedBranchEvaluation:
    control: BranchReceipt
    candidate: BranchReceipt
    proof: EvaluationProof


class PairedBranchEvaluator:
    """Evaluate one candidate through an injected paired branch runner.

    This class translates experiment receipts into the SEM evaluator contract.
    It never decides acceptance and never calls adoption.  A failed
    comparability proof is returned as evidence so the pipeline can reject it
    without pretending that the candidate was scientifically comparable.
    """

    def __init__(self, runner: BranchRunnerPort) -> None:
        self.runner = runner

    def evaluate(self, candidate: CandidateArchitecture) -> EvaluationProof:
        control = self._run(BranchRole.CONTROL, None)
        candidate_receipt = self._run(BranchRole.CANDIDATE, candidate)
        proof = build_comparability_proof(control, candidate_receipt)
        metrics = self._metrics(control, candidate_receipt, proof.valid)
        return EvaluationProof(proof, metrics)

    def evaluate_with_receipts(self, candidate: CandidateArchitecture) -> PairedBranchEvaluation:
        control = self._run(BranchRole.CONTROL, None)
        candidate_receipt = self._run(BranchRole.CANDIDATE, candidate)
        proof = build_comparability_proof(control, candidate_receipt)
        return PairedBranchEvaluation(
            control,
            candidate_receipt,
            EvaluationProof(proof, self._metrics(control, candidate_receipt, proof.valid)),
        )

    def _run(self, role: BranchRole, candidate: CandidateArchitecture | None) -> BranchReceipt:
        try:
            receipt = self.runner.run(role=role, candidate=candidate)
        except CandidateEvaluationError:
            raise
        except Exception as exc:
            raise CandidateEvaluationError(role, exc) from exc
        if not isinstance(receipt, BranchReceipt):
            raise CandidateEvaluationError(role, TypeError("branch runner returned an invalid receipt"))
        if role is BranchRole.CONTROL and candidate is not None:
            raise CandidateEvaluationError(role, ValueError("control branch received a candidate"))
        if role is BranchRole.CANDIDATE and candidate is None:
            raise CandidateEvaluationError(role, ValueError("candidate branch received no candidate"))
        return receipt

    @staticmethod
    def _metrics(
        control: BranchReceipt,
        candidate: BranchReceipt,
        comparable: bool,
    ) -> dict[str, float]:
        control_metrics = PairedBranchEvaluator._metric_map(control)
        candidate_metrics = PairedBranchEvaluator._metric_map(candidate)
        output: dict[str, float] = {"comparability.valid": float(comparable)}
        for name, value in sorted(control_metrics.items()):
            output[f"control.{name}"] = value
        for name, value in sorted(candidate_metrics.items()):
            output[f"candidate.{name}"] = value
        for name in sorted(set(control_metrics) & set(candidate_metrics)):
            output[f"delta.{name}"] = candidate_metrics[name] - control_metrics[name]
        return output

    @staticmethod
    def _metric_map(receipt: BranchReceipt) -> dict[str, float]:
        output: dict[str, float] = {}
        for name, value in receipt.metrics:
            if not name.strip():
                raise ValueError("branch receipt metric name must be non-empty")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"branch receipt metric is not finite: {name}")
            if name in output:
                raise ValueError(f"branch receipt contains duplicate metric: {name}")
            output[name] = numeric
        return output


__all__ = [
    "BranchRole",
    "BranchRunnerPort",
    "CandidateEvaluationError",
    "PairedBranchEvaluation",
    "PairedBranchEvaluator",
]
