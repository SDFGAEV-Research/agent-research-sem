from __future__ import annotations

from dataclasses import replace

import pytest

from projects.sem_paper.method.self_evolving_memory.architecture import (
    AccessMode,
    ArchitectureCompiler,
    FieldSpec,
    MemoryMode,
    MemoryNodeSpec,
    MemoryScope,
    OperatorKind,
    PredicateAtom,
    PredicateOp,
    PrimitiveType,
    RecordSelector,
    SemanticObjective,
    SourceKind,
    SourceSpec,
    TransformOpSpec,
    TransformPlan,
    TypeSpec,
)
from projects.sem_paper.method.self_evolving_memory.architecture.edits import (
    MergeNodesEdit,
    SplitChildDraft,
    SplitNodeEdit,
)
from projects.sem_paper.method.self_evolving_memory.evolution import (
    EditKind,
    OperationalVerifier,
    PrimitiveEditKind,
    StructuralCompiler,
    StructuralIntent,
)
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract


def _architecture():
    source = MemoryNodeSpec(
        "events", "Events", "Grounded events", MemoryScope.AGENT, MemoryMode.APPEND,
        (FieldSpec("event", TypeSpec(PrimitiveType.TEXT)),), (),
        frozenset({AccessMode.SEMANTIC}), (SourceSpec(SourceKind.EVIDENCE),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_MAP, objective=SemanticObjective("map events")),)),
    )
    summary = MemoryNodeSpec(
        "summary", "Summary", "Grounded summary", MemoryScope.AGENT, MemoryMode.AGGREGATE,
        (FieldSpec("statement", TypeSpec(PrimitiveType.TEXT)),), ("statement",),
        frozenset({AccessMode.SEMANTIC, AccessMode.EXACT}),
        (SourceSpec(SourceKind.NODE, node_id="events"),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_REDUCE, objective=SemanticObjective("reduce events")),)),
    )
    from projects.sem_paper.method.self_evolving_memory.architecture import MemoryArchitectureSpec
    return MemoryArchitectureSpec("1", "compiler-contract", 0, (source, summary))


def _typed_target_builder(base_generation, edits, intent):
    del base_generation, edits
    payload = intent.payload
    assert isinstance(payload, dict)
    current = payload["architecture"]
    edit = payload["architecture_edit"]
    target = ArchitectureCompiler().compile_edit(current, edit)
    contracts = tuple(
        MaterializationContract(node.node_id, node.selector, node.transform)
        for node in target.nodes
    )
    return target, contracts


def test_typed_split_primitives_are_derived_from_exact_target_diff():
    current = _architecture()
    edit = SplitNodeEdit(
        "SPLIT_NODE", "summary",
        RecordSelector((PredicateAtom("statement", PredicateOp.EQ, "grounded"),)),
        SplitChildDraft("Focused", "Focused summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
        SplitChildDraft("Other", "Other summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
    )
    candidate = StructuralCompiler(_typed_target_builder).compile(
        StructuralIntent(EditKind.SPLIT, "split evidence", {"architecture": current, "architecture_edit": edit}),
        "session:g0",
    )
    created = tuple(
        edit.target for edit in candidate.primitive_edits
        if edit.kind is PrimitiveEditKind.CREATE
    )
    retired = tuple(
        edit.target for edit in candidate.primitive_edits
        if edit.kind is PrimitiveEditKind.RETIRE
    )
    assert retired == ("summary",)
    assert len(created) == 2
    assert set(created) == set(candidate.target_spec.node_map()) - {"events"}
    OperationalVerifier().verify(candidate)


def test_typed_merge_primitives_match_merged_target_exactly():
    base = _architecture()
    split = ArchitectureCompiler().compile_edit(
        base,
        SplitNodeEdit(
            "SPLIT_NODE", "summary",
            RecordSelector((PredicateAtom("statement", PredicateOp.EQ, "grounded"),)),
            SplitChildDraft("Focused", "Focused summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
            SplitChildDraft("Other", "Other summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
        ),
    )
    children = tuple(node for node in split.nodes if node.node_id != "events")
    merge = MergeNodesEdit(
        "MERGE_NODES", children[0].node_id, children[1].node_id,
        "Merged", "Merged summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT}),
    )
    candidate = StructuralCompiler(_typed_target_builder).compile(
        StructuralIntent(EditKind.MERGE, "merge evidence", {"architecture": split, "architecture_edit": merge}),
        "session:g1",
    )
    created = tuple(
        edit.target for edit in candidate.primitive_edits
        if edit.kind is PrimitiveEditKind.CREATE
    )
    retired = tuple(
        edit.target for edit in candidate.primitive_edits
        if edit.kind is PrimitiveEditKind.RETIRE
    )
    assert len(created) == 1
    assert set(retired) == {children[0].node_id, children[1].node_id}
    assert created[0] in candidate.target_spec.node_map()
    OperationalVerifier().verify(candidate)


def test_structural_compiler_rejects_missing_legacy_fields_instead_of_defaulting():
    builder = lambda base, edits, intent: ({"base": base}, (MaterializationContract("n", {}, {}),))
    compiler = StructuralCompiler(builder)
    with pytest.raises(ValueError, match="node_id"):
        compiler.compile(StructuralIntent(EditKind.CREATE, "reason", {}), "g0")


def test_typed_structural_intent_rejects_edit_kind_mismatch():
    current = _architecture()
    wrong_edit = SplitNodeEdit(
        "SPLIT_NODE", "summary",
        RecordSelector((PredicateAtom("statement", PredicateOp.EQ, "grounded"),)),
        SplitChildDraft("Focused", "Focused summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
        SplitChildDraft("Other", "Other summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
    )
    with pytest.raises(TypeError, match="CREATE intent requires CreateNodeEdit"):
        StructuralCompiler(_typed_target_builder).compile(
            StructuralIntent(EditKind.CREATE, "reason", {"architecture": current, "architecture_edit": wrong_edit}),
            "g0",
        )


def test_typed_target_builder_drift_is_rejected():
    current = _architecture()
    edit = SplitNodeEdit(
        "SPLIT_NODE", "summary",
        RecordSelector((PredicateAtom("statement", PredicateOp.EQ, "grounded"),)),
        SplitChildDraft("Focused", "Focused summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
        SplitChildDraft("Other", "Other summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
    )
    def drifting_builder(base_generation, edits, intent):
        target, contracts = _typed_target_builder(base_generation, edits, intent)
        return replace(target, architecture_id="drifted"), contracts

    with pytest.raises(ValueError, match="drifted"):
        StructuralCompiler(drifting_builder).compile(
            StructuralIntent(EditKind.SPLIT, "reason", {"architecture": current, "architecture_edit": edit}),
            "g0",
        )


def test_operational_verifier_requires_exact_target_contract_coverage():
    current = _architecture()
    edit = SplitNodeEdit(
        "SPLIT_NODE", "summary",
        RecordSelector((PredicateAtom("statement", PredicateOp.EQ, "grounded"),)),
        SplitChildDraft("Focused", "Focused summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
        SplitChildDraft("Other", "Other summary", frozenset({AccessMode.SEMANTIC, AccessMode.EXACT})),
    )
    candidate = StructuralCompiler(_typed_target_builder).compile(
        StructuralIntent(EditKind.SPLIT, "reason", {"architecture": current, "architecture_edit": edit}),
        "g0",
    )
    incomplete = replace(candidate, materialization_contracts=candidate.materialization_contracts[:-1])
    with pytest.raises(ValueError, match="cover every target node exactly"):
        OperationalVerifier().verify(incomplete)
