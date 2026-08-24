from __future__ import annotations

from typing import Protocol

from research_platform.participant.method.api import MethodCompositionPorts, MethodEndpointPort
from research_platform.experimentation.study.api import VariantBinding
from research_platform.platform.kernel import canonical_digest

from projects.sem_paper.method.self_evolving_memory.architecture import (
    ArchitectureValidator,
    MemoryArchitectureSpec,
    SemPaperArchitecturePreset,
    build_sem_paper_architecture,
)
from projects.sem_paper.method.self_evolving_memory.evolution import CandidateArchitecture
from projects.sem_paper.method.self_evolving_memory.evolution import PrimitiveEdit, PrimitiveEditKind
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


class VariantMethodEndpointFactoryPort(Protocol):
    """Resolve a compiled experiment arm to its method endpoint."""

    def endpoint_for(
        self,
        *,
        binding: VariantBinding,
        candidate: CandidateArchitecture | None,
    ) -> MethodEndpointPort: ...


class SemPaperVariantMethodEndpointFactory:
    """Explicit provider dispatch for the compiled Core-6 arms.

    The workload adapters must not infer a method from ``VariantKind``.  This
    resolver makes the provider identity the dispatch key and keeps the
    concrete endpoint factories at the project composition boundary.  The
    RuleBased and SelfEvolve factories are intentionally separate callables;
    the current plumbing root may bind the same materializer temporarily, but
    a future rule-based implementation can be injected without touching the
    study or environment layers.
    """

    def __init__(
        self,
        *,
        fixed_endpoint: MethodEndpointPort,
        rule_based_materializer: CandidateMethodMaterializerPort,
        self_evolving_materializer: CandidateMethodMaterializerPort,
    ) -> None:
        self._fixed_endpoint = fixed_endpoint
        self._rule_based_materializer = rule_based_materializer
        self._self_evolving_materializer = self_evolving_materializer

    @staticmethod
    def _implementation_id(binding: VariantBinding) -> str:
        return binding.provider_id.rsplit(".", 1)[-1]

    def endpoint_for(
        self,
        *,
        binding: VariantBinding,
        candidate: CandidateArchitecture | None,
    ) -> MethodEndpointPort:
        implementation = self._implementation_id(binding)
        if implementation in {"FixedSeed", "fixed-memory"}:
            if candidate is not None:
                raise CandidateMethodMaterializationError(
                    "FixedSeed arm cannot receive a candidate architecture"
                )
            return self._fixed_endpoint
        if candidate is None:
            raise CandidateMethodMaterializationError(
                f"{implementation} arm requires a candidate architecture"
            )
        if implementation in {"RuleBasedEvolver", "candidate-memory"}:
            return self._rule_based_materializer.materialize(candidate)
        if implementation == "SelfEvolve":
            return self._self_evolving_materializer.materialize(candidate)
        raise CandidateMethodMaterializationError(
            f"no method endpoint provider is bound for implementation {implementation!r}"
        )


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


def build_seed_x_candidate(*, base_generation: str = "g0") -> CandidateArchitecture:
    """Build the current Paper-1 C→X structural candidate explicitly.

    The candidate is immutable experiment input: its typed target architecture
    and complete contracts are hashed before the paired branches run.  It is
    not an adoption or acceptance decision.
    """

    if not base_generation.strip():
        raise ValueError("SEM candidate base_generation is required")
    return build_seed_candidate("Seed-X", base_generation=base_generation)


def build_seed_candidate(seed_id: str, *, base_generation: str = "g0") -> CandidateArchitecture:
    """Build the typed candidate architecture for one frozen seed arm."""

    if not seed_id.strip() or not base_generation.strip():
        raise ValueError("SEM seed candidate identity is required")
    normalized = seed_id.strip().lower().replace("_", "-")
    if normalized not in {"seed-c", "seed-x"}:
        raise ValueError(f"unsupported SEM seed candidate: {seed_id!r}")
    preset = SemPaperArchitecturePreset.C if normalized == "seed-c" else SemPaperArchitecturePreset.X
    target = build_sem_paper_architecture(preset)
    contracts = tuple(
        MaterializationContract(node.node_id, node.selector, node.transform)
        for node in target.nodes
    )
    edits = () if preset is SemPaperArchitecturePreset.C else (
        PrimitiveEdit(PrimitiveEditKind.CREATE, "mem_spatial"),
        PrimitiveEdit(PrimitiveEditKind.CREATE, "mem_entity"),
        PrimitiveEdit(PrimitiveEditKind.RETIRE, "mem_world"),
        PrimitiveEdit(PrimitiveEditKind.CREATE, "mem_event"),
        PrimitiveEdit(PrimitiveEditKind.CREATE, "mem_pattern"),
        PrimitiveEdit(PrimitiveEditKind.RETIRE, "mem_experience"),
        PrimitiveEdit(PrimitiveEditKind.RETIRE, "mem_knowledge"),
        PrimitiveEdit(PrimitiveEditKind.RETIRE, "mem_procedure"),
    )
    digest = canonical_digest(target)
    return CandidateArchitecture(
        base_generation=base_generation,
        candidate_id=f"sem-paper:{normalized}-v018",
        target_spec=target,
        target_spec_digest=digest,
        primitive_edits=edits,
        materialization_contracts=contracts,
    )


__all__ = [
    "CandidateMethodMaterializationError",
    "CandidateMethodMaterializerPort",
    "VariantMethodEndpointFactoryPort",
    "SemPaperVariantMethodEndpointFactory",
    "SemPaperCandidateMethodMaterializer",
    "build_seed_candidate",
    "build_seed_x_candidate",
]
