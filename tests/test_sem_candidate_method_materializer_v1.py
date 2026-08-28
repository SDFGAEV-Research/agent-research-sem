from __future__ import annotations

import pytest

from projects.sem_paper.composition import SemPaperCandidateMethodMaterializer
from projects.sem_paper.method.self_evolving_memory.architecture import build_sem_paper_architecture
from projects.sem_paper.method.self_evolving_memory.evolution import (
    CandidateArchitecture,
    PrimitiveEdit,
    PrimitiveEditKind,
)
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract
from research_platform.participant.method.api import MethodCompositionPorts
from research_platform.platform.kernel import canonical_digest


class EndpointFactory:
    def __init__(self) -> None:
        self.bound: list[tuple[object, object]] = []

    def bind(self, implementation: object, runtime: object) -> object:
        self.bound.append((implementation, runtime))
        return object()


class Transformer:
    def transform(self, *, node, source_records):
        del node, source_records
        return ()


def _candidate() -> CandidateArchitecture:
    architecture = build_sem_paper_architecture()
    contracts = tuple(
        MaterializationContract(node.node_id, node.selector, node.transform)
        for node in architecture.nodes
    )
    return CandidateArchitecture(
        base_generation="g0",
        candidate_id="candidate-deluxe-a",
        target_spec=architecture,
        target_spec_digest=canonical_digest(architecture),
        primitive_edits=(PrimitiveEdit(PrimitiveEditKind.CREATE, "mem_candidate"),),
        materialization_contracts=contracts,
    )


def _materializer(factory: EndpointFactory) -> SemPaperCandidateMethodMaterializer:
    return SemPaperCandidateMethodMaterializer(
        method_system=MethodCompositionPorts(factory, object()),
        evolution_factory=lambda source: object(),
        evolution_provider_id="tests.evolution.v1",
        transformer=Transformer(),
    )


def test_candidate_materializer_builds_deluxe_endpoint_with_candidate_identity() -> None:
    factory = EndpointFactory()
    candidate = _candidate()
    endpoint = _materializer(factory).materialize(candidate)

    assert endpoint is not None
    implementation, runtime = factory.bound[0]
    assert implementation.configuration_digest == candidate.target_spec_digest
    assert implementation.serving_provider_id == "sem.serving.deluxe.candidate.v1"
    assert runtime.runtime_identity.runtime_id == "sem.session_runtime"


def test_candidate_materializer_rejects_tampered_target_digest() -> None:
    candidate = _candidate()
    tampered = CandidateArchitecture(
        candidate.base_generation,
        candidate.candidate_id,
        candidate.target_spec,
        "0" * 64,
        candidate.primitive_edits,
        candidate.materialization_contracts,
    )
    with pytest.raises(ValueError, match="target spec digest"):
        _materializer(EndpointFactory()).materialize(tampered)


def test_candidate_materializer_rejects_incomplete_contract_set() -> None:
    candidate = _candidate()
    incomplete = CandidateArchitecture(
        candidate.base_generation,
        candidate.candidate_id,
        candidate.target_spec,
        candidate.target_spec_digest,
        candidate.primitive_edits,
        candidate.materialization_contracts[:-1],
    )
    with pytest.raises(ValueError, match="cover exactly"):
        _materializer(EndpointFactory()).materialize(incomplete)
