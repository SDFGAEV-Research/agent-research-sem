from __future__ import annotations

import pytest

from research_platform.platform.kernel import canonical_digest
from projects.sem_paper.method.self_evolving_memory.architecture import (
    AccessMode,
    FieldSpec,
    MemoryArchitectureSpec,
    MemoryMode,
    MemoryNodeSpec,
    MemoryScope,
    OperatorKind,
    PrimitiveType,
    SourceKind,
    SourceSpec,
    SemanticObjective,
    TransformOpSpec,
    TransformPlan,
    TypeSpec,
)
from projects.sem_paper.method.self_evolving_memory.architecture.records import NodePartitionedRecord
from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore, build_evidence_record
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract
from projects.sem_paper.method.self_evolving_memory.typed_materialization import (
    TypedMaterializationError,
    TypedMaterializedGeneration,
    TypedMemoryMaterializer,
)


def _architecture() -> MemoryArchitectureSpec:
    events = MemoryNodeSpec(
        "events",
        "Events",
        "grounded event history",
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
        "derived grounded summary",
        MemoryScope.AGENT,
        MemoryMode.AGGREGATE,
        (FieldSpec("statement", TypeSpec(PrimitiveType.TEXT)),),
        ("statement",),
        frozenset({AccessMode.SEMANTIC, AccessMode.EXACT}),
        (SourceSpec(SourceKind.NODE, node_id="events"),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_REDUCE, objective=SemanticObjective("reduce grounded events")),)),
    )
    return MemoryArchitectureSpec("1", "typed-contract-test", 0, (events, summary))


def test_typed_materializer_uses_one_pinned_evidence_cut() -> None:
    store = InMemoryEvidenceStore()
    store.append(build_evidence_record("e1", 1, {"event": "first"}))

    class Source:
        def __init__(self) -> None:
            self.pin_calls = 0

        def pin(self):
            self.pin_calls += 1
            pinned = store.read_view()
            store.append(build_evidence_record("e2", 2, {"event": "late"}))
            return pinned

    class Builder:
        def build_records(self, architecture, evidence, contracts):
            del architecture, contracts
            return tuple(
                NodePartitionedRecord(
                    "events",
                    f"events:{row.evidence_id}",
                    row.sequence,
                    str(row.payload),
                    {"event": str(row.payload["event"])},
                    (row.evidence_id,),
                )
                for row in evidence.iter_rows()
            )

    source = Source()
    generation = TypedMemoryMaterializer(source, Builder()).build(
        "g1",
        base_generation="g0",
        candidate_id="candidate",
        architecture=_architecture(),
        contracts=(MaterializationContract("events", {}, {}), MaterializationContract("summary", {}, {})),
    )
    assert source.pin_calls == 1
    assert generation.source_sequence == 1
    assert tuple(record.record_id for record in generation.records) == ("events:e1",)


def test_typed_generation_document_rejects_schema_digest_and_field_type_drift() -> None:
    generation = TypedMaterializedGeneration(
        "g1",
        "g0",
        "candidate",
        _architecture(),
        1,
        "a" * 64,
        (NodePartitionedRecord("events", "events:r1", 1, "first", {"event": "first"}, ("e1",)),),
    )
    document = generation.to_document()

    tampered = dict(document)
    tampered["source_sequence"] = 2
    with pytest.raises(TypedMaterializationError, match="digest mismatch"):
        TypedMaterializedGeneration.from_document(tampered)

    unknown = dict(document)
    unknown["unexpected"] = True
    with pytest.raises(TypedMaterializationError, match="schema mismatch"):
        TypedMaterializedGeneration.from_document(unknown)

    invalid_record = dict(document)
    invalid_record["records"] = [dict(document["records"][0], sequence=True)]
    invalid_record["document_digest"] = canonical_digest(
        {key: value for key, value in invalid_record.items() if key != "document_digest"}
    )
    with pytest.raises(TypedMaterializationError, match="sequence must be a non-negative integer"):
        TypedMaterializedGeneration.from_document(invalid_record)
