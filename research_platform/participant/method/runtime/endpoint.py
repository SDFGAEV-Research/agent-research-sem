from __future__ import annotations

from dataclasses import dataclass

from research_platform.participant.method.api.runtime import (
    MethodEndpointPort,
    MethodImplementation,
    MethodRuntimeBinding,
    MethodRuntimeIdentity,
    MethodSessionRuntime,
)
from research_platform.participant.method.api.contracts import MethodIdentity, MethodSession


@dataclass(frozen=True, slots=True)
class MethodRuntimeEndpoint(MethodEndpointPort):
    implementation: MethodImplementation
    runtime: MethodSessionRuntime

    @property
    def identity(self) -> MethodIdentity:
        return self.implementation.identity

    @property
    def runtime_identity(self) -> MethodRuntimeIdentity:
        return self.runtime.runtime_identity

    @property
    def binding(self) -> MethodRuntimeBinding:
        return MethodRuntimeBinding(self.implementation.identity, self.runtime.runtime_identity)

    @property
    def binding_digest(self) -> str:
        return self.binding.digest()

    def open_session(self, *, session_id: str, services: object) -> MethodSession:
        return self.runtime.open_session(
            self.implementation,
            binding=self.binding,
            session_id=session_id,
            services=services,
        )


class DefaultMethodEndpointFactory:
    def bind(
        self,
        implementation: MethodImplementation,
        runtime: MethodSessionRuntime,
    ) -> MethodEndpointPort:
        return MethodRuntimeEndpoint(implementation, runtime)


__all__ = ["DefaultMethodEndpointFactory", "MethodRuntimeEndpoint"]
