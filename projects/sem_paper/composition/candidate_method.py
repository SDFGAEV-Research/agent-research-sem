from __future__ import annotations

from typing import Protocol

from research_platform.participant.method.api import MethodCompositionPorts, MethodEndpointPort
from research_platform.platform.kernel import canonical_digest

from projects.sem_paper.method.self_evolving_memory.architecture import ArchitectureValidator, MemoryArchitectureSpec
from projects.sem_paper.method.self_evolving_memory.evolution import CandidateArchitecture
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract
from projects.sem_paper.method.self_evolving_memory.runtime import SelfEvolvingMemoryRuntime
from projects.sem_paper.method.self_evolving_memory.session_evolution_api import SessionEvolutionFactory
from projects.sem_paper.method.self_evolving_memory.session_serving_api import SessionServingFactory
from projects.sem_paper.method.self_evolving_memory.serving_providers import build_deluxe_session_serving
from projects.sem_paper.method.self_evolving_memory.typed_builders import (
    ArchitectureDrivenTypedNodeBuilder,
    TypedSemanticNodeTransformPort,
)
from projects.sem_paper.method.self_evolving_memory.typed_materialization import build_live_typed_snapshot_factory

from .method import build_self_evolving_treatment


class CandidateMethodMaterializationError(ValueError):
    """Candidate method materialization failed before a session was opened."""


class CandidateMethodMaterializerPort(Protocol):
    def materialize(self, candidate: CandidateArchitecture) -> MethodEndpointPort: ...


class SemPaperCandidateMethodMaterializer(CandidateMethodMaterializerPort):
    """Materialize a candidate architecture into a real Deluxe method endpoint.

    The candidate's typed architecture and complete materialization contracts
    are the only source of the candidate serving surface. No baseline endpoint
    is returned when candidate materialization is absent or invalid.
    """

    def __init__(
        self,
        *,
        method_system: MethodCompositionPorts,
        evolution_factory: SessionEvolutionFactory,
        evolution_provider_id: str,
        transformer: TypedSemanticNodeTransformPort,
        runtime: SelfEvolvingMemoryRuntime | None = None,
        serving_provider_id: str = "sem.serving.deluxe.candidate.v1",
    ) -> None:
        if not evolution_provider_id.strip() or not serving_provider_id.strip():
            raise ValueError("candidate method provider identities are required")
        self._method_system = method_system
        self._evolution_factory = evolution_factory
        self._evolution_provider_id = evolution_provider_id
        self._transformer = transformer
        self._runtime = runtime
        self._serving_provider_id = serving_provider_id

    def materialize(self, candidate: CandidateArchitecture) -> MethodEndpointPort:
        if not candidate.base_generation.strip() or not candidate.candidate_id.strip():
            raise CandidateMethodMaterializationError("candidate identity is incomplete")
        if not isinstance(candidate.target_spec, MemoryArchitectureSpec):
            raise CandidateMethodMaterializationError(
                "Deluxe candidate requires a typed MemoryArchitectureSpec target"
            )
        if canonical_digest(candidate.target_spec) != candidate.target_spec_digest:
            raise CandidateMethodMaterializationError("candidate target spec digest is invalid")
        ArchitectureValidator().verify(candidate.target_spec)
        contracts = tuple(candidate.materialization_contracts)
        if not contracts or any(not isinstance(contract, MaterializationContract) for contract in contracts):
            raise CandidateMethodMaterializationError(
                "candidate must provide typed materialization contracts for every node"
            )
        node_ids = {node.node_id for node in candidate.target_spec.nodes}
        contract_ids = tuple(contract.node_id for contract in contracts)
        if len(contract_ids) != len(set(contract_ids)) or set(contract_ids) != node_ids:
            raise CandidateMethodMaterializationError(
                "candidate materialization contracts must cover exactly the target architecture"
            )
        snapshot_factory = build_live_typed_snapshot_factory(
            architecture=candidate.target_spec,
            contracts=contracts,
            builder=ArchitectureDrivenTypedNodeBuilder(self._transformer),
            candidate_id=candidate.candidate_id,
        )
        return build_self_evolving_treatment(
            method_system=self._method_system,
            evolution_factory=self._evolution_factory,
            evolution_provider_id=self._evolution_provider_id,
            serving_factory=build_deluxe_session_serving,
            serving_provider_id=self._serving_provider_id,
            runtime=self._runtime,
            configuration_digest=candidate.target_spec_digest,
            deluxe_snapshot_factory=snapshot_factory,
        )


__all__ = [
    "CandidateMethodMaterializationError",
    "CandidateMethodMaterializerPort",
    "SemPaperCandidateMethodMaterializer",
]
