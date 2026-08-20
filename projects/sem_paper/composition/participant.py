from __future__ import annotations

from dataclasses import dataclass

from research_platform.participant.core.api.contracts import (
    ParticipantImplementationIdentity,
    ParticipantRuntimeBinding,
    ParticipantSessionRuntimeIdentity,
)
from research_platform.participant.core.api.runtime import (
    ParticipantResolverPort,
    ParticipantRuntimeEndpoint,
    ParticipantRuntimeHandle,
)
from research_platform.participant.method.api import MethodEndpointPort, MethodIdentity, MethodSession


def _participant_implementation_identity(identity: MethodIdentity) -> ParticipantImplementationIdentity:
    return ParticipantImplementationIdentity(
        kind="method",
        participant_id=identity.method_id,
        implementation_version=identity.implementation_version,
        abi_version=identity.abi_version,
        schema_version=identity.schema_version,
        artifact_digest=identity.artifact_digest,
    )


def _participant_runtime_identity(identity: object) -> ParticipantSessionRuntimeIdentity:
    fields = ("runtime_id", "runtime_version", "abi_version", "artifact_digest")
    values = tuple(getattr(identity, field, "") for field in fields)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise TypeError("Paper-1 method runtime identity cannot be projected to Participant runtime identity")
    return ParticipantSessionRuntimeIdentity(*values)


@dataclass(frozen=True, slots=True)
class SemPaperMethodParticipantEndpoint(ParticipantRuntimeEndpoint):
    """Project-owned projection of one method endpoint into Participant's ABI."""

    method_endpoint: MethodEndpointPort
    implementation_identity: ParticipantImplementationIdentity
    runtime_identity: ParticipantSessionRuntimeIdentity

    @property
    def identity(self) -> MethodIdentity:
        return self.method_endpoint.identity

    def open_session(self, *, session_id: str, services: object) -> MethodSession:
        return self.method_endpoint.open_session(session_id=session_id, services=services)


@dataclass(frozen=True, slots=True)
class SemPaperMethodParticipantVariant:
    """One explicitly selectable Paper-1 treatment at the Participant seam."""

    treatment_id: str
    endpoint: SemPaperMethodParticipantEndpoint
    binding: ParticipantRuntimeBinding


class SemPaperMethodResolver(ParticipantResolverPort):
    """Resolve Paper-1 method treatments by complete projected identity."""

    def __init__(self, treatments: tuple[tuple[str, MethodEndpointPort], ...]) -> None:
        variants: list[SemPaperMethodParticipantVariant] = []
        by_identity: dict[tuple[str, str], SemPaperMethodParticipantVariant] = {}
        seen_treatments: set[str] = set()
        for treatment_id, endpoint in treatments:
            if not treatment_id.strip() or treatment_id in seen_treatments:
                raise ValueError(f"duplicate or empty Paper-1 treatment id: {treatment_id!r}")
            if not isinstance(endpoint, MethodEndpointPort):
                raise TypeError("Paper-1 treatment endpoint does not satisfy MethodEndpointPort")
            seen_treatments.add(treatment_id)
            implementation = _participant_implementation_identity(endpoint.identity)
            runtime = _participant_runtime_identity(endpoint.runtime_identity)
            projected = SemPaperMethodParticipantEndpoint(endpoint, implementation, runtime)
            binding = ParticipantRuntimeBinding("method", implementation, runtime, "")
            key = (implementation.digest(), runtime.digest())
            if key in by_identity:
                raise ValueError(
                    "Paper-1 treatments project to the same participant implementation/runtime identity: "
                    f"{treatment_id!r} and {by_identity[key].treatment_id!r}"
                )
            variant = SemPaperMethodParticipantVariant(treatment_id, projected, binding)
            variants.append(variant)
            by_identity[key] = variant
        if not variants:
            raise ValueError("Paper-1 requires at least one method treatment")
        self._variants = tuple(variants)
        self._by_identity = by_identity

    @property
    def variants(self) -> tuple[SemPaperMethodParticipantVariant, ...]:
        return self._variants

    def resolve(self, binding: ParticipantRuntimeBinding) -> ParticipantRuntimeHandle:
        if binding.implementation.kind != "method":
            raise KeyError(f"Paper-1 method resolver does not own participant kind={binding.implementation.kind!r}")
        key = (binding.implementation.digest(), binding.runtime.digest())
        try:
            variant = self._by_identity[key]
        except KeyError as exc:
            raise KeyError(
                "unknown Paper-1 method implementation/runtime identity: "
                f"{binding.implementation.participant_id}:{binding.runtime.runtime_id}"
            ) from exc
        if variant.endpoint.implementation_identity != binding.implementation:
            raise ValueError("Paper-1 method implementation identity collision")
        if variant.endpoint.runtime_identity != binding.runtime:
            raise ValueError("Paper-1 method runtime identity collision")
        return ParticipantRuntimeHandle(binding, variant.endpoint)


__all__ = [
    "SemPaperMethodParticipantEndpoint",
    "SemPaperMethodParticipantVariant",
    "SemPaperMethodResolver",
]
