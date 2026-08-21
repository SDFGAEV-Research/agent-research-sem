from __future__ import annotations

from research_platform.participant.method.api import MethodCompositionPorts, MethodEndpointPort

from projects.sem_paper.method.self_evolving_memory.implementation import SelfEvolvingMemoryImplementation
from projects.sem_paper.method.self_evolving_memory.runtime import SelfEvolvingMemoryRuntime
from projects.sem_paper.method.self_evolving_memory.session_evolution_api import SessionEvolutionFactory
from projects.sem_paper.method.self_evolving_memory.session_evolution_runtime import DisabledSessionEvolutionFactory
from projects.sem_paper.method.self_evolving_memory.session_serving_api import DeluxeSnapshotFactory, SessionServingFactory
from projects.sem_paper.method.self_evolving_memory.session_state_memory import InMemorySEMSessionStateFactory
from projects.sem_paper.method.self_evolving_memory.serving_providers import build_hybrid_session_serving


def _bind_sem(
    *,
    system_ports: MethodCompositionPorts,
    serving_factory: SessionServingFactory,
    serving_provider_id: str | None,
    evolution_factory: SessionEvolutionFactory,
    evolution_provider_id: str,
    runtime: SelfEvolvingMemoryRuntime | None,
    deluxe_snapshot_factory: DeluxeSnapshotFactory | None,
    configuration_digest: str | None,
) -> MethodEndpointPort:
    implementation = SelfEvolvingMemoryImplementation(
        serving_factory=serving_factory,
        evolution_factory=evolution_factory,
        serving_provider_id=serving_provider_id,
        evolution_provider_id=evolution_provider_id,
        deluxe_snapshot_factory=deluxe_snapshot_factory,
        configuration_digest=configuration_digest,
    )
    session_runtime = runtime or SelfEvolvingMemoryRuntime(
        InMemorySEMSessionStateFactory(),
        system_ports.observation_outbox_factory,
    )
    return system_ports.endpoint_factory.bind(implementation, session_runtime)


def build_fixed_memory_method(
    *,
    system_ports: MethodCompositionPorts,
    serving_factory: SessionServingFactory = build_hybrid_session_serving,
    serving_provider_id: str | None = None,
    runtime: SelfEvolvingMemoryRuntime | None = None,
    deluxe_snapshot_factory: DeluxeSnapshotFactory | None = None,
    configuration_digest: str | None = None,
) -> MethodEndpointPort:
    """SEM fixed-treatment composition: serving enabled, structural evolution disabled."""

    return _bind_sem(
        system_ports=system_ports,
        serving_factory=serving_factory,
        serving_provider_id=serving_provider_id,
        evolution_factory=DisabledSessionEvolutionFactory(),
        evolution_provider_id="sem.evolution.disabled.v1",
        runtime=runtime,
        deluxe_snapshot_factory=deluxe_snapshot_factory,
        configuration_digest=configuration_digest,
    )


def build_self_evolving_memory_method(
    *,
    system_ports: MethodCompositionPorts,
    evolution_factory: SessionEvolutionFactory,
    evolution_provider_id: str,
    serving_factory: SessionServingFactory = build_hybrid_session_serving,
    serving_provider_id: str | None = None,
    runtime: SelfEvolvingMemoryRuntime | None = None,
    deluxe_snapshot_factory: DeluxeSnapshotFactory | None = None,
    configuration_digest: str | None = None,
) -> MethodEndpointPort:
    """SEM self-evolving treatment; evolution authority must be explicitly composed."""

    if not evolution_provider_id.strip():
        raise ValueError("self-evolving SEM requires stable evolution_provider_id")
    return _bind_sem(
        system_ports=system_ports,
        serving_factory=serving_factory,
        serving_provider_id=serving_provider_id,
        evolution_factory=evolution_factory,
        evolution_provider_id=evolution_provider_id,
        runtime=runtime,
        deluxe_snapshot_factory=deluxe_snapshot_factory,
        configuration_digest=configuration_digest,
    )


__all__ = ["build_fixed_memory_method", "build_self_evolving_memory_method"]
