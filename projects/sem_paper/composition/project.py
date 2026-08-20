from __future__ import annotations

from dataclasses import dataclass

from research_platform.observability.logging.api import LogSinkPort
from research_platform.participant.method.api import MethodCompositionPorts, MethodEndpointPort
from research_platform.portfolio.project.api import ProjectDefinition

from projects.sem_paper.api import PROJECT_DEFINITION
from projects.sem_paper.method.self_evolving_memory.runtime import SelfEvolvingMemoryRuntime
from projects.sem_paper.method.self_evolving_memory.session_evolution_api import SessionEvolutionFactory
from projects.sem_paper.method.self_evolving_memory.session_serving_api import SessionServingFactory
from projects.sem_paper.method.self_evolving_memory.serving_providers import build_hybrid_session_serving

from .logging import bind_project_logging
from .method import build_fixed_memory_treatment, build_self_evolving_treatment


@dataclass(frozen=True, slots=True)
class SemPaperCompositionPorts:
    """Platform seams and Paper-1 adapters supplied to the project root."""

    method_system: MethodCompositionPorts
    log_sink: LogSinkPort
    evolution_factory: SessionEvolutionFactory
    evolution_provider_id: str
    serving_factory: SessionServingFactory = build_hybrid_session_serving
    serving_provider_id: str | None = None
    fixed_runtime: SelfEvolvingMemoryRuntime | None = None
    self_evolving_runtime: SelfEvolvingMemoryRuntime | None = None


@dataclass(frozen=True, slots=True)
class SemPaperBindings:
    """Fully bound Paper-1 project surface; no session is opened here."""

    definition: ProjectDefinition
    logging: LogSinkPort
    fixed_memory: MethodEndpointPort
    self_evolving: MethodEndpointPort


def compose_sem_paper(ports: SemPaperCompositionPorts) -> SemPaperBindings:
    """Bind platform interfaces to the Paper-1 method without running it."""

    return SemPaperBindings(
        definition=PROJECT_DEFINITION,
        logging=bind_project_logging(ports.log_sink),
        fixed_memory=build_fixed_memory_treatment(
            method_system=ports.method_system,
            serving_factory=ports.serving_factory,
            serving_provider_id=ports.serving_provider_id,
            runtime=ports.fixed_runtime,
        ),
        self_evolving=build_self_evolving_treatment(
            method_system=ports.method_system,
            evolution_factory=ports.evolution_factory,
            evolution_provider_id=ports.evolution_provider_id,
            serving_factory=ports.serving_factory,
            serving_provider_id=ports.serving_provider_id,
            runtime=ports.self_evolving_runtime,
        ),
    )


__all__ = ["SemPaperBindings", "SemPaperCompositionPorts", "compose_sem_paper"]
