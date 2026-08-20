from __future__ import annotations

from dataclasses import dataclass

from research_platform.participant.core.api.contracts import ParticipantSessionRuntimeIdentity

from ..runtime import MinecraftEnvironmentRuntime


@dataclass(frozen=True, slots=True)
class MinecraftParticipantRuntimeAdapter:
    """Composition-only adapter from MC runtime identity to participant ABI.

    The MC environment package remains independent of participant internals.
    Only this composition leaf imports the participant binding identity needed
    by the generic participant resolver.
    """

    runtime: MinecraftEnvironmentRuntime

    @property
    def runtime_identity(self) -> ParticipantSessionRuntimeIdentity:
        identity = self.runtime.runtime_identity
        return ParticipantSessionRuntimeIdentity(
            runtime_id=identity.runtime_id,
            runtime_version=identity.runtime_version,
            abi_version=identity.abi_version,
            artifact_digest=identity.artifact_digest,
        )

    def open_session(self, implementation: object, *, session_id: str, services: object) -> object:
        return self.runtime.open_session(implementation, session_id=session_id, services=services)


__all__ = ["MinecraftParticipantRuntimeAdapter"]
