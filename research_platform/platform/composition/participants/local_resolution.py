from __future__ import annotations

from research_platform.participant.core.api.contracts import ParticipantRuntimeBinding
from research_platform.participant.core.api.runtime import ParticipantRuntimeHandle

from research_platform.participant.core.implementation.catalog import ParticipantImplementationCatalog
from research_platform.participant.core.implementation.configuration import ParticipantConfigurationCatalog
from research_platform.participant.core.runtime.runtime_catalog import ParticipantSessionRuntimeCatalog
from research_platform.participant.core.runtime.runtime_endpoint import LocalParticipantRuntimeEndpoint


class LocalParticipantResolver:
    """Composition-only join of implementation, session runtime and immutable configuration catalogs."""

    def __init__(
        self,
        implementations: ParticipantImplementationCatalog,
        runtimes: ParticipantSessionRuntimeCatalog,
        configurations: ParticipantConfigurationCatalog,
    ) -> None:
        self._implementations = implementations
        self._runtimes = runtimes
        self._configurations = configurations

    def resolve(self, binding: ParticipantRuntimeBinding) -> ParticipantRuntimeHandle:
        registered_implementation = self._implementations.resolve(binding.implementation)
        registered_runtime = self._runtimes.resolve(binding.runtime)
        configuration = self._configurations.resolve(binding.configuration_digest)
        implementation = registered_implementation.factory(configuration)
        runtime = registered_runtime.factory()
        if runtime.runtime_identity != binding.runtime:
            raise ValueError("participant session runtime factory identity drift")
        endpoint = LocalParticipantRuntimeEndpoint(
            binding.implementation,
            binding.runtime,
            implementation,
            runtime,
        )
        return ParticipantRuntimeHandle(binding, endpoint)


__all__ = ["LocalParticipantResolver"]
