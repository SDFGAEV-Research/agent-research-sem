from __future__ import annotations

from research_platform.participant.binding.runtime.configuration import ParticipantConfigurationCatalog
from research_platform.participant.binding.runtime.local_resolver import LocalParticipantResolver
from research_platform.participant.definition.runtime.catalog import ParticipantImplementationCatalog
from research_platform.participant.session.runtime.runtime_catalog import ParticipantSessionRuntimeCatalog
from research_platform.participant.session.runtime.runtime_endpoint import LocalParticipantRuntimeEndpoint


def build_local_participant_resolver(
    implementations: ParticipantImplementationCatalog,
    runtimes: ParticipantSessionRuntimeCatalog,
    configurations: ParticipantConfigurationCatalog,
) -> LocalParticipantResolver:
    """Bind local leaf authorities to the dependency-inverted resolver port."""

    return LocalParticipantResolver(
        implementations,
        runtimes,
        configurations,
        LocalParticipantRuntimeEndpoint,
    )


__all__ = ["build_local_participant_resolver"]
