from __future__ import annotations

from dataclasses import dataclass

from research_platform.participant.core.api.contracts import (
    ParticipantImplementationIdentity,
    ParticipantSessionRuntimeIdentity,
)
from research_platform.participant.core.api.runtime import ParticipantSessionRuntime


@dataclass(frozen=True, slots=True)
class LocalParticipantRuntimeEndpoint:
    """Local join of one implementation object and one independent session runtime."""

    implementation_identity: ParticipantImplementationIdentity
    runtime_identity: ParticipantSessionRuntimeIdentity
    implementation: object
    runtime: ParticipantSessionRuntime

    @property
    def identity(self) -> object:
        try:
            return self.implementation.identity
        except AttributeError as exc:
            raise TypeError("participant implementation does not expose its domain identity") from exc

    def open_session(self, *, session_id: str, services: object) -> object:
        return self.runtime.open_session(
            self.implementation,
            session_id=session_id,
            services=services,
        )
