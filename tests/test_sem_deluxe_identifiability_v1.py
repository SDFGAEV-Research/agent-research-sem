from __future__ import annotations

from dataclasses import dataclass, replace

from projects.sem_paper.method.self_evolving_memory.architecture import (
    AccessMode,
    FieldSpec,
    MemoryArchitectureSpec,
    MemoryMode,
    MemoryNodeSpec,
    MemoryScope,
    PrimitiveType,
    SourceKind,
    SourceSpec,
    TransformOpSpec,
    TransformPlan,
    TypeSpec,
    OperatorKind,
)
from projects.sem_paper.method.self_evolving_memory.evolution.identifiability import (
    ArchitectureIdentifiabilityEngine,
)


@dataclass(frozen=True)
class _Record:
    payload: dict[str, object]
    source_refs: tuple[str, ...]


def _architecture(purpose: str = "grounded task events") -> MemoryArchitectureSpec:
    events = MemoryNodeSpec(
        "events",
        "Events",
        purpose,
        MemoryScope.AGENT,
        MemoryMode.APPEND,
        (FieldSpec("event", TypeSpec(PrimitiveType.TEXT)),),
        (),
        frozenset({AccessMode.SEMANTIC}),
        (SourceSpec(SourceKind.EVIDENCE),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_MAP),)),
    )
    summary = MemoryNodeSpec(
        "summary",
        "Summary",
        "derived events",
        MemoryScope.AGENT,
        MemoryMode.AGGREGATE,
        (FieldSpec("statement", TypeSpec(PrimitiveType.TEXT)),),
        ("statement",),
        frozenset({AccessMode.SEMANTIC}),
        (SourceSpec(SourceKind.NODE, node_id="events"),),
        TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_REDUCE),)),
    )
    return MemoryArchitectureSpec("1", "identifiability", 0, (events, summary))


def test_identifiability_exact_fingerprint_is_read_only() -> None:
    architecture = _architecture()
    store = {
        "events": (_Record({"event": "found tree"}, ("e1",)),),
        "summary": (_Record({"statement": "tree nearby"}, ("events:r1",)),),
    }
    engine = ArchitectureIdentifiabilityEngine()

    fingerprint = engine.fingerprint(architecture, store=store)
    report = engine.compare(architecture, architecture, store_left=store, store_right=store)

    assert fingerprint.node_count == 2
    assert fingerprint.edge_count == 2
    assert report.exact is True
    assert report.equivalence_level == "E0_EXACT"
    assert report.likely_functionally_equivalent is True
    assert architecture.generation == 0


def test_identifiability_distinguishes_semantic_change_without_accepting_or_mutating() -> None:
    base = _architecture()
    changed = replace(
        base,
        nodes=(replace(base.nodes[0], purpose="combat outcomes"), base.nodes[1]),
    )
    report = ArchitectureIdentifiabilityEngine().compare(base, changed)

    assert report.exact is False
    assert report.equivalence_level in {"E1_SEMANTIC", "DISTINCT"}
    assert report.likely_functionally_equivalent is False
    assert base.nodes[0].purpose == "grounded task events"
