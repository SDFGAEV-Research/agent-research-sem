from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from projects.sem_paper.method.self_evolving_memory.architecture import (
    AccessMode,
    ArchitectureCompileError,
    ArchitectureCompiler,
    ArchitectureValidator,
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
from projects.sem_paper.method.self_evolving_memory.typed_materialization import TypedMaterializationError, TypedMemoryMaterializer


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
        (SourceSpec(SourceKind.EVIDENCE, evidence_channel="AUDIT"),),
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
