from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoleCanaryResult:
    role: str
    total: int
    passed: int
    critical_total: int
    critical_passed: int
    contract_errors: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


@dataclass(frozen=True, slots=True)
class PerformanceSample:
    concurrency: int
    ttft_p50: float
    ttft_p99: float
    tpot_p50: float
    tpot_p99: float
    output_tokens_per_second: float
    error_rate: float


@dataclass(frozen=True, slots=True)
class QualificationEvidence:
    model_stack_digest: str
    canaries: tuple[RoleCanaryResult, ...]
    performance: tuple[PerformanceSample, ...]
    exact_output_reproducibility_checked: bool
    long_context_checked: bool
    tool_call_checked: bool

    def all_critical_pass(self) -> bool:
        return all(c.critical_passed == c.critical_total for c in self.canaries)


@dataclass(frozen=True, slots=True)
class QualificationPolicy:
    minimum_role_pass_rate: float = 0.98
    require_zero_critical_failures: bool = True
    max_error_rate: float = 0.001


@dataclass(frozen=True, slots=True)
class QualificationDecision:
    qualified: bool
    reasons: tuple[str, ...]


def evaluate_qualification(evidence: QualificationEvidence, policy: QualificationPolicy) -> QualificationDecision:
    reasons: list[str] = []
    for c in evidence.canaries:
        if c.pass_rate < policy.minimum_role_pass_rate:
            reasons.append(f"role {c.role} pass_rate {c.pass_rate:.4f} below {policy.minimum_role_pass_rate:.4f}")
        if policy.require_zero_critical_failures and c.critical_passed != c.critical_total:
            reasons.append(f"role {c.role} has critical failures")
    for p in evidence.performance:
        if p.error_rate > policy.max_error_rate:
            reasons.append(f"concurrency {p.concurrency} error_rate {p.error_rate:.6f} above {policy.max_error_rate:.6f}")
    if not evidence.exact_output_reproducibility_checked:
        reasons.append("exact-output reproducibility not checked")
    if not evidence.tool_call_checked:
        reasons.append("tool-call contract not checked")
    return QualificationDecision(not reasons, tuple(reasons))
