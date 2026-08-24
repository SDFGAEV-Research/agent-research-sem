from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import math

from research_platform.platform.kernel import canonical_digest


class VariantKind(StrEnum):
    CONTROL = "control"
    TREATMENT = "treatment"
    ABLATION = "ablation"
    EXTERNAL_BASELINE = "external_baseline"


@dataclass(frozen=True, slots=True)
class StudyVariantSpec:
    variant_id: str
    kind: VariantKind
    implementation_id: str
    configuration_digest: str
    budget_tier: str = "standard"
    ablates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.variant_id.strip() or not self.implementation_id.strip():
            raise ValueError("study variant identity is required")
        if not self.configuration_digest.strip():
            raise ValueError("study variant configuration digest is required")
        if not self.budget_tier.strip():
            raise ValueError("study variant budget tier is required")


@dataclass(frozen=True, slots=True)
class StudyProtocol:
    """Frozen scientific design consumed by every environment adapter."""

    study_id: str
    workload_id: str
    variants: tuple[StudyVariantSpec, ...]
    repetitions: int
    seed_schedule_digest: str
    metric_names: tuple[str, ...]
    task_manifest_digest: str
    budget_tiers: tuple[str, ...] = ("standard",)
    protocol_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.study_id.strip() or not self.workload_id.strip():
            raise ValueError("study protocol identity is required")
        if not self.variants:
            raise ValueError("study protocol requires at least one variant")
        if len({item.variant_id for item in self.variants}) != len(self.variants):
            raise ValueError("study protocol contains duplicate variants")
        if self.repetitions <= 0:
            raise ValueError("study protocol repetitions must be positive")
        if not self.seed_schedule_digest.strip() or not self.task_manifest_digest.strip():
            raise ValueError("study protocol seed/task identities are required")
        if not self.metric_names or len(set(self.metric_names)) != len(self.metric_names):
            raise ValueError("study protocol metric_names must be non-empty and unique")
        if not self.budget_tiers or len(set(self.budget_tiers)) != len(self.budget_tiers):
            raise ValueError("study protocol budget tiers must be non-empty and unique")
        unknown_tiers = {item.budget_tier for item in self.variants} - set(self.budget_tiers)
        if unknown_tiers:
            raise ValueError(f"study variants use undeclared budget tiers: {sorted(unknown_tiers)}")
        object.__setattr__(
            self,
            "protocol_digest",
            canonical_digest(
                {
                    "study_id": self.study_id,
                    "workload_id": self.workload_id,
                    "variants": self.variants,
                    "repetitions": self.repetitions,
                    "seed_schedule_digest": self.seed_schedule_digest,
                    "metric_names": self.metric_names,
                    "task_manifest_digest": self.task_manifest_digest,
                    "budget_tiers": self.budget_tiers,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class StudyAssignment:
    study_id: str
    variant_id: str
    repetition: int
    seed: str
    assignment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.study_id.strip() or not self.variant_id.strip() or not self.seed.strip():
            raise ValueError("study assignment identity is required")
        if self.repetition < 0:
            raise ValueError("study assignment repetition cannot be negative")
        object.__setattr__(
            self,
            "assignment_digest",
            canonical_digest(
                {
                    "study_id": self.study_id,
                    "variant_id": self.variant_id,
                    "repetition": self.repetition,
                    "seed": self.seed,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class StudyExecutionUnit:
    """One reproducible repetition group passed to an environment adapter."""

    study_id: str
    repetition: int
    assignments: tuple[StudyAssignment, ...]
    unit_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.study_id.strip() or self.repetition < 0 or not self.assignments:
            raise ValueError("study execution unit identity is incomplete")
        if any(item.study_id != self.study_id for item in self.assignments):
            raise ValueError("study execution unit contains another study")
        if any(item.repetition != self.repetition for item in self.assignments):
            raise ValueError("study execution unit mixes repetitions")
        digests = tuple(item.assignment_digest for item in self.assignments)
        if len(digests) != len(set(digests)):
            raise ValueError("study execution unit contains duplicate assignments")
        object.__setattr__(
            self,
            "unit_digest",
            canonical_digest(
                {
                    "study_id": self.study_id,
                    "repetition": self.repetition,
                    "assignments": digests,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class StudyMatrixExecutionReport:
    """Complete observations and aggregates for one frozen study matrix."""

    protocol_digest: str
    observations: tuple["StudyMetricObservation", ...]
    aggregates: tuple["StudyMetricAggregate", ...]
    binding_digest: str | None = None
    plan_digest: str | None = None

    def __post_init__(self) -> None:
        if len(self.protocol_digest) != 64:
            raise ValueError("study matrix report protocol digest must be SHA-256")
        for name, value in (("binding_digest", self.binding_digest), ("plan_digest", self.plan_digest)):
            if value is not None and len(value) != 64:
                raise ValueError(f"study matrix report {name} must be SHA-256 when present")
        if self.plan_digest is not None and self.binding_digest is None:
            raise ValueError("study matrix report plan digest requires a binding digest")


@dataclass(frozen=True, slots=True)
class StudyMetricObservation:
    assignment: StudyAssignment
    metrics: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        names = [name for name, _ in self.metrics]
        if not names or len(names) != len(set(names)):
            raise ValueError("study metric observation requires unique metrics")
        if any(not name.strip() or not math.isfinite(float(value)) for name, value in self.metrics):
            raise ValueError("study metric observation contains an invalid metric")


@dataclass(frozen=True, slots=True)
class StudyMetricAggregate:
    study_id: str
    variant_id: str
    metric_name: str
    count: int
    mean: float
    sample_variance: float
    standard_error: float

    def __post_init__(self) -> None:
        if not self.study_id.strip() or not self.variant_id.strip() or not self.metric_name.strip():
            raise ValueError("study aggregate identity is required")
        if self.count <= 0 or not all(
            math.isfinite(float(value))
            for value in (self.mean, self.sample_variance, self.standard_error)
        ):
            raise ValueError("study aggregate statistics are invalid")


__all__ = [
    "StudyAssignment",
    "StudyExecutionUnit",
    "StudyMatrixExecutionReport",
    "StudyMetricAggregate",
    "StudyMetricObservation",
    "StudyProtocol",
    "StudyVariantSpec",
    "VariantKind",
]
