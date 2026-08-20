from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from research_platform.participant.core.api.contracts import ParticipantSessionRuntimeIdentity
from research_platform.participant.core.api.runtime import ParticipantSessionRuntime


ParticipantSessionRuntimeFactory = Callable[[], ParticipantSessionRuntime]


@dataclass(frozen=True, slots=True)
class RegisteredParticipantSessionRuntime:
    identity: ParticipantSessionRuntimeIdentity
    factory: ParticipantSessionRuntimeFactory


class ParticipantSessionRuntimeCatalog:
    """Build-time authority for session runtimes, independent of participant implementations."""

    def __init__(self) -> None:
        self._runtimes: dict[str, RegisteredParticipantSessionRuntime] = {}

    def register(
        self,
        identity: ParticipantSessionRuntimeIdentity,
        factory: ParticipantSessionRuntimeFactory,
    ) -> None:
        key = identity.digest()
        if key in self._runtimes:
            raise ValueError(f"duplicate participant session runtime: {identity.runtime_id}:{identity.runtime_version}")
        self._runtimes[key] = RegisteredParticipantSessionRuntime(identity, factory)

    def resolve(self, identity: ParticipantSessionRuntimeIdentity) -> RegisteredParticipantSessionRuntime:
        try:
            registered = self._runtimes[identity.digest()]
        except KeyError as exc:
            raise KeyError(
                f"unknown participant session runtime: {identity.runtime_id}:{identity.runtime_version}"
            ) from exc
        if registered.identity != identity:
            raise ValueError("participant session runtime catalog identity collision")
        return registered

    def identities(self) -> tuple[ParticipantSessionRuntimeIdentity, ...]:
        return tuple(sorted((row.identity for row in self._runtimes.values()), key=lambda row: row.digest()))


__all__ = [
    "ParticipantSessionRuntimeCatalog",
    "ParticipantSessionRuntimeFactory",
    "RegisteredParticipantSessionRuntime",
]
