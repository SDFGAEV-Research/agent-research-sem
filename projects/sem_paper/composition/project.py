from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.architecture.api.capabilities import (
    LOGGING_SYSTEM_V1,
    METHOD_COMPOSITION_PORTS_V1,
)
from research_platform.governance.architecture.api.capability_composition import (
    BindingPlan,
    CapabilityCompositionPlannerPort,
    CapabilityRequirement,
    CompositionContract,
    CompositionIdentity,
    CompositionSubject,
    RequirementAddress,
    interface_contract_digest,
)
from research_platform.observability.logging.record.api import (
    LoggingSystemBinding,
    LoggingSystemPort,
)
from research_platform.participant.method.api import (
    MethodCompositionPorts,
    MethodEndpointPort,
    MethodSystemBinding,
)
from research_platform.portfolio.project.api import ProjectDefinition
from research_platform.scope.api import ScopeIdentity, ScopeKind

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

    method_system: MethodSystemBinding
    logging: LoggingSystemBinding
    planner: CapabilityCompositionPlannerPort
    scope: ScopeIdentity
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
    logging: LoggingSystemPort
    fixed_memory: MethodEndpointPort
    self_evolving: MethodEndpointPort


@dataclass(frozen=True, slots=True)
class SemPaperProjectComposition:
    """Paper-owned bindings and the frozen plan for imported platform seams."""

    bindings: SemPaperBindings
    plan: BindingPlan


def compose_sem_paper(ports: SemPaperCompositionPorts) -> SemPaperProjectComposition:
    """Bind platform interfaces to the Paper-1 method without running it."""

    if ports.scope.kind is not ScopeKind.PROJECT:
        raise ValueError("Paper-1 composition requires a project scope")
    subject = CompositionSubject.project_subject(
        PROJECT_DEFINITION.identity.project_id,
        PROJECT_DEFINITION.identity.version,
    )
    logging_requirement = CapabilityRequirement(
        RequirementAddress(subject, "logging-system"),
        ports.scope,
        LOGGING_SYSTEM_V1,
        interface_contract_digest(LoggingSystemPort),
    )
    method_requirement = CapabilityRequirement(
        RequirementAddress(subject, "method-composition-ports"),
        ports.scope,
        METHOD_COMPOSITION_PORTS_V1,
        interface_contract_digest(MethodCompositionPorts),
    )
    plan = ports.planner.freeze(
        CompositionIdentity(
            "project.sem-paper-1",
            ports.scope,
            owner=subject,
        ),
        (
            CompositionContract(
                subject,
                ports.scope,
                requirements=(logging_requirement, method_requirement),
            ),
        ),
        imported_offers=(
            ports.logging.offer,
            ports.method_system.offer,
        ),
    )
    bindings = SemPaperBindings(
        definition=PROJECT_DEFINITION,
        logging=bind_project_logging(ports.logging.logging),
        fixed_memory=build_fixed_memory_treatment(
            method_system=ports.method_system.ports,
            serving_factory=ports.serving_factory,
            serving_provider_id=ports.serving_provider_id,
            runtime=ports.fixed_runtime,
        ),
        self_evolving=build_self_evolving_treatment(
            method_system=ports.method_system.ports,
            evolution_factory=ports.evolution_factory,
            evolution_provider_id=ports.evolution_provider_id,
            serving_factory=ports.serving_factory,
            serving_provider_id=ports.serving_provider_id,
            runtime=ports.self_evolving_runtime,
        ),
    )
    return SemPaperProjectComposition(bindings, plan)


__all__ = [
    "SemPaperBindings",
    "SemPaperCompositionPorts",
    "SemPaperProjectComposition",
    "compose_sem_paper",
]
