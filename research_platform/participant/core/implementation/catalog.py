from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from research_platform.participant.core.api.contracts import ParticipantConfigurationArtifact, ParticipantImplementationIdentity


ParticipantImplementationFactory = Callable[[ParticipantConfigurationArtifact], object]


@dataclass(frozen=True, slots=True)
class RegisteredParticipantImplementation:
    identity: ParticipantImplementationIdentity
    factory: ParticipantImplementationFactory


class ParticipantImplementationCatalog:
    """Build-time implementation authority. It knows factories, but no Study/run/tmux/control identity."""

    def __init__(self) -> None:
        self._implementations: dict[str, RegisteredParticipantImplementation] = {}

    def register(
        self,
        identity: ParticipantImplementationIdentity,
        factory: ParticipantImplementationFactory,
    ) -> None:
        key = identity.digest()
        if key in self._implementations:
            raise ValueError(f"duplicate participant implementation: {identity.kind}:{identity.participant_id}:{identity.implementation_version}")
        self._implementations[key] = RegisteredParticipantImplementation(identity, factory)

    def resolve(self, identity: ParticipantImplementationIdentity) -> RegisteredParticipantImplementation:
        try:
            registered = self._implementations[identity.digest()]
        except KeyError as exc:
            raise KeyError(
                f"unknown participant implementation: {identity.kind}:{identity.participant_id}:{identity.implementation_version}"
            ) from exc
        if registered.identity != identity:
            raise ValueError("participant implementation catalog identity collision")
        return registered

    def identities(self) -> tuple[ParticipantImplementationIdentity, ...]:
        return tuple(sorted((row.identity for row in self._implementations.values()), key=lambda row: row.digest()))


__all__ = [
    "ParticipantImplementationCatalog",
    "ParticipantImplementationFactory",
    "RegisteredParticipantImplementation",
]
