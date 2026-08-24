"""Executable experiment-plan boundary.

The plan is the only place where scientific arm identity is compiled into a
runtime provider. Environment adapters receive bindings, never interpret
Core-6 names or VariantKind relationships themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from research_platform.platform.kernel import canonical_digest

from .contracts import StudyAssignment, StudyExecutionUnit, StudyMetricObservation, StudyProtocol, StudyVariantSpec


class VariantExecutionProvider(Protocol):
    def provider_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class VariantBinding:
    variant: StudyVariantSpec
    seed_id: str
    provider_id: str
    ablation_policy_id: str
    comparator_role: str
    binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.seed_id, self.provider_id, self.ablation_policy_id, self.comparator_role)
        ):
            raise ValueError("variant binding identity is incomplete")
        object.__setattr__(
            self,
            "binding_digest",
            canonical_digest(
                {
                    "variant": self.variant,
                    "seed_id": self.seed_id,
                    "provider_id": self.provider_id,
                    "ablation_policy_id": self.ablation_policy_id,
                    "comparator_role": self.comparator_role,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class VariantExecutionRequest:
    """The only runtime request a variant provider is allowed to consume."""

    plan_digest: str
    unit: StudyExecutionUnit
    assignment: StudyAssignment
    binding: VariantBinding

    def __post_init__(self) -> None:
        if len(self.plan_digest) != 64:
            raise ValueError("variant execution request requires a plan digest")
        if self.assignment not in self.unit.assignments:
            raise ValueError("variant execution request assignment is outside its unit")
        if self.assignment.variant_id != self.binding.variant.variant_id:
            raise ValueError("variant execution request binding does not match assignment")


@dataclass(frozen=True, slots=True)
class VariantExecutionReceipt:
    """Provider output with no environment-specific leakage."""

    assignment: StudyAssignment
    metrics: tuple[tuple[str, float], ...]

    def as_observation(self) -> StudyMetricObservation:
        return StudyMetricObservation(self.assignment, self.metrics)


@dataclass(frozen=True, slots=True)
class ExperimentPlan:
    protocol: StudyProtocol
    bindings: tuple[VariantBinding, ...]
    plan_digest: str
    protocol_digest: str = field(init=False)
    binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        declared_by_id = {item.variant_id: item for item in self.protocol.variants}
        declared = set(declared_by_id)
        bound = {item.variant.variant_id for item in self.bindings}
        if declared != bound or len(bound) != len(self.bindings):
            raise ValueError("experiment plan bindings do not exactly cover protocol variants")
        if any(
            declared_by_id[item.variant.variant_id] != item.variant
            for item in self.bindings
        ):
            raise ValueError("experiment plan binding variant spec diverges from the protocol")
        protocol_digest = self.protocol.protocol_digest
        binding_digest = canonical_digest(tuple(item.binding_digest for item in self.bindings))
        expected_plan_digest = canonical_digest(
            {"protocol_digest": protocol_digest, "binding_digest": binding_digest}
        )
        if self.plan_digest != expected_plan_digest:
            raise ValueError("experiment plan digest is not authoritative")
        object.__setattr__(self, "protocol_digest", protocol_digest)
        object.__setattr__(self, "binding_digest", binding_digest)

    @classmethod
    def compile(cls, protocol: StudyProtocol, bindings: tuple[VariantBinding, ...]) -> "ExperimentPlan":
        binding_digest = canonical_digest(tuple(item.binding_digest for item in bindings))
        return cls(
            protocol,
            bindings,
            canonical_digest(
                {"protocol_digest": protocol.protocol_digest, "binding_digest": binding_digest}
            ),
        )

    def assert_consistent(self) -> None:
        """Recompute both protocol and binding identities at the execution edge."""

        expected = type(self).compile(self.protocol, self.bindings)
        if expected.protocol_digest != self.protocol_digest:
            raise ValueError("experiment plan protocol digest drifted")
        if expected.binding_digest != self.binding_digest:
            raise ValueError("experiment plan binding digest drifted")
        if expected.plan_digest != self.plan_digest:
            raise ValueError("experiment plan digest drifted")

    def binding_for(self, variant_id: str) -> VariantBinding:
        matches = tuple(item for item in self.bindings if item.variant.variant_id == variant_id)
        if len(matches) != 1:
            raise KeyError(f"experiment plan has no unique binding for variant {variant_id!r}")
        return matches[0]


__all__ = [
    "ExperimentPlan",
    "VariantBinding",
    "VariantExecutionProvider",
    "VariantExecutionReceipt",
    "VariantExecutionRequest",
]
