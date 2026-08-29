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
class ResourceQualificationMeasurements:
    peak_gpu_memory_bytes_per_device: int
    peak_host_memory_bytes: int
    max_qualified_concurrency: int

    def __post_init__(self) -> None:
        for field in ("peak_gpu_memory_bytes_per_device", "peak_host_memory_bytes", "max_qualified_concurrency"):
            value = getattr(self, field)
            if type(value) is not int or value <= 0:
                raise ValueError(f"qualification resource measurement {field} must be a positive integer")


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
    require_exact_output_reproducibility: bool = True
    require_long_context_checked: bool = False
    require_tool_call_checked: bool = True


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
    if policy.require_exact_output_reproducibility and not evidence.exact_output_reproducibility_checked:
        reasons.append("exact-output reproducibility not checked")
    if policy.require_long_context_checked and not evidence.long_context_checked:
        reasons.append("long-context contract not checked")
    if policy.require_tool_call_checked and not evidence.tool_call_checked:
        reasons.append("tool-call contract not checked")
    return QualificationDecision(not reasons, tuple(reasons))
