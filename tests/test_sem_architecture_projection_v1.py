from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace

import pytest

from projects.sem_paper.method.self_evolving_memory.architecture import (
    AccessMode,
    ArchitectureCompileError,
    ArchitectureCompiler,
    ArchitectureValidator,
    EvidenceSourceChannel,
    FieldSpec,
    MemoryArchitectureSpec,
    MemoryMode,
    MemoryNodeSpec,
    MemoryScope,
    OperatorKind,
    PredicateAtom,
    PredicateOp,
    PrimitiveType,
    RecordSelector,
    SourceKind,
    SourceRequirement,
    SourceSpec,
    SemanticObjective,
    TransformOpSpec,
    TransformPlan,
    TypeSpec,
    architecture_digest,
    architecture_from_dict,
    architecture_to_dict,
)
from projects.sem_paper.method.self_evolving_memory.architecture.edits import (
    CreateNodeEdit,
    MergeNodesEdit,
    MemoryNodeDraft,
    RetireNodeEdit,
    SplitChildDraft,
    SplitNodeEdit,
)
from projects.sem_paper.method.self_evolving_memory.architecture.projection import (
    ArchitectureProjectionError,
    NodePartitionedDeluxeSnapshot,
    project_deluxe_architecture,
)
from projects.sem_paper.method.self_evolving_memory.deluxe.runtime.serving import DeluxeMemoryServingService
from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore, build_evidence_record
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract
from projects.sem_paper.method.self_evolving_memory.typed_materialization import (
    TypedGenerationArtifactError,
    TypedGenerationDriftError,
    TypedMaterializationError,
    TypedMemoryMaterializer,
    TypedMaterializerAdapter,
    build_live_typed_snapshot_factory,
    build_adopted_typed_snapshot_factory,
    build_persisted_adopted_typed_snapshot_factory,
)
from projects.sem_paper.method.self_evolving_memory.adoption_typed import AtomicTypedGenerationArtifactSource
from projects.sem_paper.method.self_evolving_memory.adoption import AtomicAdoptionService, GenerationAllocator
from projects.sem_paper.method.self_evolving_memory.evolution import CandidateArchitecture, EvaluationProof, PrimitiveEdit, PrimitiveEditKind
from research_platform.data.state.api import AggregateValue
from research_platform.data.state.runtime import InMemoryAtomicStateStore
from research_platform.experimentation.evaluation.api import ComparabilityProof
from projects.sem_paper.method.self_evolving_memory.implementation import SelfEvolvingMemoryImplementation
from projects.sem_paper.method.self_evolving_memory.serving_providers import build_deluxe_session_serving
from projects.sem_paper.method.self_evolving_memory.session_serving import ReadOnlyDeluxeServingSessionSource
from projects.sem_paper.method.self_evolving_memory.architecture.projection import NodePartitionedDeluxeSource
from projects.sem_paper.method.self_evolving_memory.session_evolution_runtime import DisabledSessionEvolutionFactory
from projects.sem_paper.method.self_evolving_memory.typed_materialization import TypedMaterializedGeneration
from projects.sem_paper.method.self_evolving_memory.composition import build_self_evolving_memory_method
from research_platform.participant.method.runtime import InMemoryMethodObservationSink
from research_platform.participant.method.api import MethodServices, RecallRequest
from research_platform.platform.kernel import ExecutionContext
from tests_support import default_method_composition_ports


def _architecture() -> MemoryArchitectureSpec:
    source = MemoryNodeSpec(
        "events",
        "Events",
        "Grounded task events",
        MemoryScope.AGENT,
        MemoryMode.APPEND,
        (FieldSpec("event", TypeSpec(PrimitiveType.TEXT)),),
        (),
        frozenset({AccessMode.SEMANTIC}),
        (SourceSpec(SourceKind.EVIDENCE),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_MAP, objective=SemanticObjective("map grounded events")),)),
    )
    summary = MemoryNodeSpec(
        "summary",
        "Summary",
        "Derived grounded summary",
        MemoryScope.AGENT,
        MemoryMode.AGGREGATE,
        (FieldSpec("statement", TypeSpec(PrimitiveType.TEXT)),),
        ("statement",),
        frozenset({AccessMode.SEMANTIC, AccessMode.EXACT}),
        (SourceSpec(SourceKind.NODE, node_id="events"),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_REDUCE, objective=SemanticObjective("reduce grounded events")),)),
    )
    return MemoryArchitectureSpec("1", "paper1", 0, (source, summary))


@dataclass(frozen=True)
class _Record:
    node_id: str
    record_id: str
    sequence: int
    text: str
    payload: dict[str, object]
    source_refs: tuple[str, ...] = ()


class _TypedBuilder:
    def build_records(self, architecture, evidence, contracts):
        return (
            _Record("events", "events:r1", 1, "found tree", {"event": "found tree"}, ("e1",)),
            _Record("summary", "summary:r1", 2, "tree is nearby", {"statement": "tree is nearby"}, ("events:r1",)),
        )


def test_migrated_ir_validates_and_projects_to_deluxe_snapshot():
    architecture = _architecture()
    ArchitectureValidator().verify(architecture)
    snapshot = project_deluxe_architecture(architecture)
    assert snapshot.generation == "paper1:g0"
    assert snapshot.generation_number == 0
    assert {node.node_id for node in snapshot.nodes} == {"events", "summary"}


def test_migrated_ir_round_trips_source_requirements_and_selectors():
    architecture = _architecture()
    summary = architecture.get("summary")
    updated_summary = replace(
        summary,
        selector=RecordSelector((PredicateAtom("statement", PredicateOp.EQ, "grounded"),)),
        transform=replace(
            summary.transform,
            source_requirements=(
                SourceRequirement("events", (("event", TypeSpec(PrimitiveType.TEXT)),)),
            ),
        ),
    )
    enriched = replace(
        architecture,
        nodes=tuple(updated_summary if node.node_id == "summary" else node for node in architecture.nodes),
    )
    ArchitectureValidator().verify(enriched)
    restored = architecture_from_dict(architecture_to_dict(enriched))
    assert architecture_digest(restored) == architecture_digest(enriched)
    assert restored.get("summary").selector == enriched.get("summary").selector
    assert restored.get("summary").transform.source_requirements == enriched.get("summary").transform.source_requirements


def test_architecture_identity_inputs_are_deeply_snapshotted_and_digest_stable():
    params = {"weights": [1, {"source": "events"}]}
    selector_value = {"labels": ["grounded"]}
    architecture = _architecture()
    summary = architecture.get("summary")
    frozen_summary = replace(
        summary,
        selector=RecordSelector((PredicateAtom("statement", PredicateOp.IN, selector_value),)),
        transform=TransformPlan(
            (
                TransformOpSpec(
                    OperatorKind.SEMANTIC_REDUCE,
                    params=params,
                    objective=SemanticObjective("reduce grounded events"),
                ),
            )
        ),
    )
    frozen = replace(architecture, nodes=(architecture.get("events"), frozen_summary))
    before = architecture_digest(frozen)

    params["weights"][1]["source"] = "mutated"  # type: ignore[index]
    selector_value["labels"].append("external-mutation")

    assert architecture_digest(frozen) == before
    document = architecture_to_dict(frozen)
    assert architecture_digest(architecture_from_dict(deepcopy(document))) == before
    assert document["nodes"][1]["transform"]["ops"][0]["weights"] == [1, {"source": "events"}]
    assert document["nodes"][1]["selector"]["all_of"][0]["value"] == {"labels": ["grounded"]}


def test_architecture_identity_values_are_read_only_after_construction():
    operation = TransformOpSpec(OperatorKind.PROJECT, params={"nested": {"value": 1}})
    atom = PredicateAtom("field", PredicateOp.EQ, {"nested": [1]})
    with pytest.raises(TypeError):
        operation.params["new"] = 2  # type: ignore[index]
    with pytest.raises(TypeError):
        operation.params["nested"]["value"] = 2  # type: ignore[index]
    with pytest.raises(TypeError):
        atom.value["nested"] += (2,)  # type: ignore[index,operator]


def test_architecture_contracts_reject_noncanonical_runtime_shapes():
    with pytest.raises(ValueError, match="typed enums"):
        TypeSpec("TEXT")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="evidence channel"):
        SourceSpec(SourceKind.EVIDENCE, evidence_channel="MEMORY")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="predicate op"):
        PredicateAtom("field", "EQ", "value")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        TransformOpSpec(OperatorKind.PROJECT, params={"weight": float("nan")})
    with pytest.raises(ValueError, match="keys"):
        TransformOpSpec(OperatorKind.PROJECT, params={1: "value"})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="typed tuple"):
        MemoryArchitectureSpec("1", "id", 0, [])  # type: ignore[arg-type]


def test_node_partition_is_explicit_and_serving_uses_pinned_architecture():
    architecture = project_deluxe_architecture(_architecture())
    projected = NodePartitionedDeluxeSnapshot(
        architecture,
        (_Record("events", "r1", 1, "found tree", {"event": "found tree"}),),
    )
    result = DeluxeMemoryServingService(
        type("Source", (), {"open_deluxe_snapshot": lambda self: projected})()
    ).recall("tree", limit=1)
    assert result.selected_nodes == ("events",)
    assert "found tree" in result.context_text


def test_projection_rejects_flat_or_unknown_node_records():
    architecture = project_deluxe_architecture(_architecture())
    with pytest.raises(ArchitectureProjectionError, match="outside pinned architecture"):
        NodePartitionedDeluxeSnapshot(
            architecture,
            (_Record("flat-evidence", "r1", 1, "not a node", {"event": "not a node"}),),
        )


def test_typed_architecture_compiler_creates_and_retires_only_leaf_nodes():
    architecture = _architecture()
    compiler = ArchitectureCompiler()
    draft = MemoryNodeDraft(
        "Extra",
        "Extra grounded event view",
        MemoryScope.AGENT,
        MemoryMode.APPEND,
        (FieldSpec("event", TypeSpec(PrimitiveType.TEXT)),),
        (),
        frozenset({AccessMode.SEMANTIC}),
        (SourceSpec(SourceKind.EVIDENCE),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_MAP, objective=SemanticObjective("map")),)),
    )
    created = compiler.compile_edit(architecture, CreateNodeEdit("CREATE_NODE", draft))
    created_id = next(node.node_id for node in created.nodes if node.node_id not in {"events", "summary"})
    retired = compiler.compile_edit(created, RetireNodeEdit("RETIRE_NODE", created_id))
    assert retired.generation == 2
    with pytest.raises(ArchitectureCompileError, match="leaf"):
        compiler.compile_edit(architecture, RetireNodeEdit("RETIRE_NODE", "events"))


def test_typed_architecture_compiler_preserves_split_merge_partition_semantics():
    architecture = _architecture()
    compiler = ArchitectureCompiler()
    split = compiler.compile_edit(
        architecture,
        SplitNodeEdit(
            "SPLIT_NODE",
            "summary",
            RecordSelector((PredicateAtom("statement", PredicateOp.EQ, "grounded"),)),
            SplitChildDraft("Grounded", "Grounded summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
            SplitChildDraft("Other", "Other summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
        ),
    )
    children = tuple(node for node in split.nodes if node.node_id not in {"events"})
    assert len(children) == 2
    merged = compiler.compile_edit(
        split,
        MergeNodesEdit("MERGE_NODES", children[0].node_id, children[1].node_id, "Summary", "Merged summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
    )
    assert len(merged.nodes) == 2


def test_validator_rejects_current_without_business_key_and_audit_source():
    base = _architecture()
    current = MemoryNodeSpec(
        "current",
        "Current",
        "Bad current node",
        MemoryScope.WORLD,
        MemoryMode.CURRENT,
        (FieldSpec("state", TypeSpec(PrimitiveType.TEXT)),),
        (),
        frozenset({AccessMode.SEMANTIC}),
        (SourceSpec(SourceKind.EVIDENCE, evidence_channel=EvidenceSourceChannel.AUDIT),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_MAP, objective=SemanticObjective("bad")),)),
    )
    errors = ArchitectureValidator().report(MemoryArchitectureSpec("1", "bad", 0, base.nodes + (current,)))
    assert {error.code for error in errors} >= {"ARCH_CURRENT_KEY", "ARCH_CONTROL_SOURCE"}


def test_typed_materializer_requires_exact_contracts_and_builds_deluxe_snapshot():
    store = InMemoryEvidenceStore()
    store.append(build_evidence_record("e1", 1, {"event": "found tree"}))
    contracts = (
        MaterializationContract("events", {"event": "*"}, {"op": "SEMANTIC_MAP"}),
        MaterializationContract("summary", {"event": "*"}, {"op": "SEMANTIC_REDUCE"}),
    )
    generation = TypedMemoryMaterializer(store, _TypedBuilder()).build(
        "prepared-1",
        base_generation="g0",
        candidate_id="candidate-1",
        architecture=_architecture(),
        contracts=contracts,
    )
    snapshot = generation.deluxe_snapshot()
    assert snapshot.node_ids() == ("events", "summary")
    assert tuple(snapshot.iter_records("summary"))[0].source_refs == ("events:r1",)


def test_typed_materializer_never_falls_back_when_builder_or_contract_is_missing():
    store = InMemoryEvidenceStore()
    with pytest.raises(TypedMaterializationError, match="explicit node builder"):
        TypedMemoryMaterializer(store, object())
    materializer = TypedMemoryMaterializer(store, _TypedBuilder())
    with pytest.raises(TypedMaterializationError, match="cover exactly"):
        materializer.build(
            "prepared-1",
            base_generation="g0",
            candidate_id="candidate-1",
            architecture=_architecture(),
            contracts=(MaterializationContract("events", {}, {}),),
        )


def test_live_typed_snapshot_factory_projects_one_pinned_jmem_cut_without_writing_back():
    store = InMemoryEvidenceStore()
    store.append(build_evidence_record("e1", 1, {"event": "found tree"}))

    class Builder:
        def build_records(self, architecture, evidence, contracts):
            del architecture, contracts
            return tuple(
                _Record(
                    "events",
                    f"events:{row.evidence_id}",
                    row.sequence,
                    str(row.payload),
                    {"event": str(row.payload["event"])},
                    (row.evidence_id,),
                )
                for row in evidence.iter_rows()
            )

    class Cell:
        def open_serving_cut(self):
            return "session:g0", store.read_view()

    factory = build_live_typed_snapshot_factory(
        architecture=_architecture(),
        contracts=(
            MaterializationContract("events", {}, {}),
            MaterializationContract("summary", {}, {}),
        ),
        builder=Builder(),
    )
    source = factory(Cell())
    first = source.open_deluxe_snapshot()
    assert first.generation == "session:g0"
    assert first.node_ids() == ("events",)
    assert tuple(first.iter_records("events"))[0].source_refs == ("e1",)

    store.append(build_evidence_record("e2", 2, {"event": "found cave"}))
    assert len(tuple(first.iter_records("events"))) == 1
    second = source.open_deluxe_snapshot()
    assert len(tuple(second.iter_records("events"))) == 2


def test_typed_materializer_rejects_untraceable_live_records():
    store = InMemoryEvidenceStore()
    store.append(build_evidence_record("e1", 1, {"event": "found tree"}))

    class UntraceableBuilder:
        def build_records(self, architecture, evidence, contracts):
            del architecture, evidence, contracts
            return (_Record("events", "events:r1", 1, "untraceable", {"event": "untraceable"}),)

    with pytest.raises(TypedMaterializationError, match="no source_refs"):
        TypedMemoryMaterializer(store, UntraceableBuilder()).build(
            "g1",
            base_generation="g0",
            candidate_id="candidate",
            architecture=_architecture(),
            contracts=(
                MaterializationContract("events", {}, {}),
                MaterializationContract("summary", {}, {}),
            ),
        )


def test_deluxe_composition_requires_an_explicit_snapshot_factory():
    with pytest.raises(ValueError, match="explicit typed snapshot factory"):
        SelfEvolvingMemoryImplementation(
            evolution_factory=object(),
            evolution_provider_id="evolution.test.v1",
            serving_factory=build_deluxe_session_serving,
            serving_provider_id="deluxe.test.v1",
        )


def test_deluxe_session_source_delegates_node_snapshot_to_project_provider():
    store = InMemoryEvidenceStore()

    class Cell:
        def open_serving_cut(self):
            return "paper1:g0", store.read_view()

    architecture = project_deluxe_architecture(_architecture())
    snapshot = NodePartitionedDeluxeSnapshot(architecture, ())
    seen = []

    def factory(cell):
        seen.append(cell)
        return NodePartitionedDeluxeSource(snapshot)

    source = ReadOnlyDeluxeServingSessionSource(Cell(), factory)
    assert source.open_deluxe_snapshot() is snapshot
    assert len(seen) == 1
    assert source.open_snapshot().generation == "paper1:g0"


def test_adopted_typed_generation_source_rejects_generation_drift():
    store = InMemoryEvidenceStore()
    store.append(build_evidence_record("e1", 1, {"event": "found tree"}))
    generation = TypedMemoryMaterializer(store, _TypedBuilder()).build(
        "prepared-1",
        base_generation="g0",
        candidate_id="candidate-1",
        architecture=_architecture(),
        contracts=(
            MaterializationContract("events", {}, {}),
            MaterializationContract("summary", {}, {}),
        ),
    )

    class Cell:
        def __init__(self, current):
            self.current = current

        def current_generation(self):
            return self.current

    source = build_adopted_typed_snapshot_factory(generation)(Cell("prepared-1"))
    assert source.open_deluxe_snapshot().generation == "prepared-1"
    drifted = Cell("prepared-2")
    with pytest.raises(TypedGenerationDriftError, match="not adopted"):
        build_adopted_typed_snapshot_factory(generation)(drifted).open_deluxe_snapshot()


def test_typed_generation_is_persisted_inside_the_existing_atomic_adoption_payload():
    evidence = InMemoryEvidenceStore()
    evidence.append(build_evidence_record("e1", 1, {"event": "found tree"}))
    architecture = _architecture()
    contracts = (
        MaterializationContract("events", {}, {}),
        MaterializationContract("summary", {}, {}),
    )
    candidate = CandidateArchitecture(
        "g0",
        "candidate-typed",
        architecture,
        architecture_digest(architecture),
        (PrimitiveEdit(PrimitiveEditKind.CREATE, "summary"),),
        contracts,
    )
    state = InMemoryAtomicStateStore(
        (
            AggregateValue(AtomicAdoptionService.ARCH, 1, "g0", "arch", {"old": True}),
            AggregateValue(AtomicAdoptionService.LEDGER, 1, "g0", "ledger", ()),
        )
    )
    service = AtomicAdoptionService(
        state,
        TypedMaterializerAdapter(TypedMemoryMaterializer(evidence, _TypedBuilder())),
        GenerationAllocator(),
    )
    proof = EvaluationProof(ComparabilityProof(True, "pair", (), "cp", "w", "env", "task"), {})
    adopted = service.adopt(candidate, proof)
    payload = state.read(AtomicAdoptionService.ARCH).payload
    assert state.read(AtomicAdoptionService.ARCH).generation == adopted
    assert payload["typed_generation"]["generation"] == adopted
    restored = TypedMaterializedGeneration.from_document(payload["typed_generation"])
    assert restored.architecture.architecture_id == architecture.architecture_id
    assert tuple(restored.deluxe_snapshot().node_ids()) == ("events", "summary")


def test_persisted_typed_artifact_reloads_through_atomic_state_after_adoption():
    evidence = InMemoryEvidenceStore()
    evidence.append(build_evidence_record("e1", 1, {"event": "found tree"}))
    architecture = _architecture()
    candidate = CandidateArchitecture(
        "g0",
        "candidate-persisted",
        architecture,
        architecture_digest(architecture),
        (PrimitiveEdit(PrimitiveEditKind.CREATE, "summary"),),
        (MaterializationContract("events", {}, {}), MaterializationContract("summary", {}, {})),
    )
    state = InMemoryAtomicStateStore(
        (
            AggregateValue(AtomicAdoptionService.ARCH, 1, "g0", "arch", {"old": True}),
            AggregateValue(AtomicAdoptionService.LEDGER, 1, "g0", "ledger", ()),
        )
    )
    generation = AtomicAdoptionService(
        state,
        TypedMaterializerAdapter(TypedMemoryMaterializer(evidence, _TypedBuilder())),
        GenerationAllocator(),
    ).adopt(
        candidate,
        EvaluationProof(ComparabilityProof(True, "pair-persisted", (), "cp", "w", "env", "task"), {}),
    )
    artifacts = AtomicTypedGenerationArtifactSource(state, architecture_aggregate=AtomicAdoptionService.ARCH)
    restored = artifacts.load(generation)

    class Cell:
        def current_generation(self):
            return generation

    source = build_persisted_adopted_typed_snapshot_factory(artifacts)(Cell())
    assert source.open_deluxe_snapshot().generation == generation
    with pytest.raises(TypedGenerationArtifactError, match="does not match"):
        artifacts.load("not-adopted")
    assert restored.candidate_id == "candidate-persisted"


def test_deluxe_treatment_is_reachable_through_the_real_sem_session_assembly():
    architecture = _architecture()
    generation = TypedMaterializedGeneration(
        "g0",
        "g0",
        "candidate-0",
        architecture,
        1,
        "evidence-digest",
        (
            _Record("events", "events:r1", 1, "found tree", {"event": "found tree"}),
            _Record("summary", "summary:r1", 2, "tree nearby", {"statement": "tree nearby"}),
        ),
    )
    endpoint = build_self_evolving_memory_method(
        system_ports=default_method_composition_ports(),
        evolution_factory=DisabledSessionEvolutionFactory(),
        evolution_provider_id="evolution.disabled.deluxe.test.v1",
        serving_factory=build_deluxe_session_serving,
        serving_provider_id="deluxe.session.test.v1",
        deluxe_snapshot_factory=build_adopted_typed_snapshot_factory(generation),
    )
    session = endpoint.open_session(
        session_id="deluxe-session",
        services=MethodServices(InMemoryMethodObservationSink()),
    )
    result = session.recall(RecallRequest("found tree", ExecutionContext("run", "trace", "span"), 2))
    assert result.method_generation == "g0"
    assert "found tree" in result.context_text
    session.close()

@pytest.mark.parametrize(
    "case",
    (
        "format_version_number",
        "generation_boolean",
        "generation_string",
        "nodes_tuple",
        "field_required_string",
        "schema_tuple",
        "access_tuple",
        "transform_ops_tuple",
        "source_event_types_tuple",
        "source_channel_number",
        "selector_negated_string",
        "unknown_top_level_field",
        "legacy_seed_contract_version",
        "legacy_single_transform_op",
    ),
)
def test_architecture_decoder_rejects_coercive_or_noncanonical_documents(case: str) -> None:
    document = deepcopy(architecture_to_dict(_architecture()))
    node = document["nodes"][0]
    if case == "format_version_number":
        document["format_version"] = 1
    elif case == "generation_boolean":
        document["generation"] = True
    elif case == "generation_string":
        document["generation"] = "1"
    elif case == "nodes_tuple":
        document["nodes"] = tuple(document["nodes"])
    elif case == "field_required_string":
        node["schema"][0]["required"] = "false"
    elif case == "schema_tuple":
        node["schema"] = tuple(node["schema"])
    elif case == "access_tuple":
        node["access"] = tuple(node["access"])
    elif case == "transform_ops_tuple":
        node["transform"]["ops"] = tuple(node["transform"]["ops"])
    elif case == "source_event_types_tuple":
        node["sources"][0]["event_types"] = ()
    elif case == "source_channel_number":
        node["sources"][0]["channel"] = 1
    elif case == "selector_negated_string":
        node["selector"] = {"all_of": [], "negated": "false"}
    elif case == "unknown_top_level_field":
        document["unexpected"] = True
    elif case == "legacy_seed_contract_version":
        document["seed_contract_version"] = document.pop("format_version")
    elif case == "legacy_single_transform_op":
        operation = node["transform"]["ops"][0]
        node["transform"] = dict(operation)
    with pytest.raises(ValueError):
        architecture_from_dict(document)

def test_architecture_decoder_rejects_duplicate_access_normalization() -> None:
    document = deepcopy(architecture_to_dict(_architecture()))
    access = document["nodes"][0]["access"]
    document["nodes"][0]["access"] = [access[0], access[0]]
    with pytest.raises(ValueError, match="node access entries must be unique"):
        architecture_from_dict(document)
