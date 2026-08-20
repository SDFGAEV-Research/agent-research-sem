from __future__ import annotations

from research_platform.participant.method.api import MethodCompositionPorts, MethodEndpointPort

from projects.sem_paper.method.self_evolving_memory.composition import (
    build_fixed_memory_method,
    build_self_evolving_memory_method,
)
from projects.sem_paper.method.self_evolving_memory.runtime import SelfEvolvingMemoryRuntime
from projects.sem_paper.method.self_evolving_memory.session_evolution_api import SessionEvolutionFactory
from projects.sem_paper.method.self_evolving_memory.session_serving_api import SessionServingFactory
from projects.sem_paper.method.self_evolving_memory.serving_providers import build_hybrid_session_serving


def build_fixed_memory_treatment(
    *,
    method_system: MethodCompositionPorts,
    serving_factory: SessionServingFactory = build_hybrid_session_serving,
    serving_provider_id: str | None = None,
    runtime: SelfEvolvingMemoryRuntime | None = None,
) -> MethodEndpointPort:
    return build_fixed_memory_method(
        system_ports=method_system,
        serving_factory=serving_factory,
        serving_provider_id=serving_provider_id,
        runtime=runtime,
    )


def build_self_evolving_treatment(
    *,
    method_system: MethodCompositionPorts,
    evolution_factory: SessionEvolutionFactory,
    evolution_provider_id: str,
    serving_factory: SessionServingFactory = build_hybrid_session_serving,
    serving_provider_id: str | None = None,
    runtime: SelfEvolvingMemoryRuntime | None = None,
) -> MethodEndpointPort:
    return build_self_evolving_memory_method(
        system_ports=method_system,
        evolution_factory=evolution_factory,
        evolution_provider_id=evolution_provider_id,
        serving_factory=serving_factory,
        serving_provider_id=serving_provider_id,
        runtime=runtime,
    )


__all__ = ["build_fixed_memory_treatment", "build_self_evolving_treatment"]
