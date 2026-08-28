from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pytest

from projects.sem_paper.method.self_evolving_memory.analysis import (
    analyze_architecture_basin,
    trajectory_report,
)
from projects.sem_paper.method.self_evolving_memory.architecture import (
    AccessMode,
    FieldSpec,
    MemoryArchitectureSpec,
    MemoryMode,
    MemoryNodeSpec,
    MemoryScope,
    PrimitiveType,
    TransformPlan,
    TypeSpec,
)
from projects.sem_paper.method.self_evolving_memory.deluxe.api import (
    CapabilityState,
    DeluxeArchitectureSnapshot,
    DeluxeNodeDescriptor,
)
from projects.sem_paper.method.self_evolving_memory.deluxe.runtime import (
    ArchitectureLineageGraph,
    CapabilityRegistry,
    EvidenceGovernance,
    EvidenceIndex,
    EvidenceTier,
)
from projects.sem_paper.method.self_evolving_memory.evidence_api import EvidenceRecord
from projects.sem_paper.method.self_evolving_memory.evidence_memory import build_evidence_record
from projects.sem_paper.method.self_evolving_memory.evolution import (
    ArchitectureGarbageCollector,
    EditKind,
    EvolutionOutcome,
)


def _architecture(generation: int = 0) -> MemoryArchitectureSpec:
    return MemoryArchitectureSpec(
        "1",
        "completion",
        generation,
        (
            MemoryNodeSpec(
                "events",
                "Events",
                "grounded events",
                MemoryScope.AGENT,
                MemoryMode.APPEND,
                (FieldSpec("event", TypeSpec(PrimitiveType.TEXT)),),
                (),
                frozenset({AccessMode.SEMANTIC}),
                (),
                TransformPlan(()),
            ),
            MemoryNodeSpec(
                "summary",
                "Summary",
                "derived events",
                MemoryScope.AGENT,
                MemoryMode.CURRENT,
                (FieldSpec("event", TypeSpec(PrimitiveType.TEXT)),),
                ("event",),
                frozenset({AccessMode.SEMANTIC}),
                (),
                TransformPlan(()),
            ),
        ),
    )


def test_evidence_index_and_governance_are_jmem_only_and_rebuildable() -> None:
    rows = (
        build_evidence_record("e1", 1, {"event_type": "OBSERVATION", "value": "oak"}),
        build_evidence_record("e2", 2, {"event_type": "ACTION", "value": "craft"}),
    )
    index = EvidenceIndex()
    index.rebuild(rows)
    assert index.stats()["memory_events"] == 2
    assert tuple(row.evidence_id for row in index.query_event_types(("ACTION",))) == ("e2",)
    decisions = EvidenceGovernance().classify(rows)
    assert all(item.reconstructible for item in decisions)
    assert decisions[-1].tier is EvidenceTier.HOT
    with pytest.raises(TypeError):
        index.add(object())  # type: ignore[arg-type]


def test_architecture_lineage_and_basin_are_read_only_analysis() -> None:
    lineage = ArchitectureLineageGraph()
    lineage.record_transition(0, 1, "CREATE")
    lineage.record_transition(1, 2, "SPLIT")
    assert lineage.path_to_root(2) == (2, 1, 0)
    basin = analyze_architecture_basin((
        ("run-a", _architecture()),
        ("run-b", _architecture(1)),
    ))
    assert basin["n_runs"] == 2
    assert basin["functional_equifinality_possible"] is False
    report = trajectory_report((
        EvolutionOutcome("no_edit", "g0", "g0", EditKind.NO_EDIT),
        EvolutionOutcome("adopted", "g0", "g1", EditKind.CREATE),
    ))
    assert report["accepted_generations"] == ["g1"]


def test_deluxe_gc_only_proposes_leaf_retirement() -> None:
    architecture = DeluxeArchitectureSnapshot(
        "g1",
        "a" * 64,
        (
            DeluxeNodeDescriptor("events", "events", ("semantic",), ("text",)),
            DeluxeNodeDescriptor("summary", "summary", ("semantic",), ("text",)),
        ),
        generation_number=1,
    )
    registry = CapabilityRegistry()
    registry.sync_architecture(architecture)
    capability_id = registry.capability_for_node("summary")
    assert capability_id is not None
    registry.lifecycle[capability_id].state = CapabilityState.RETIRE_CANDIDATE
    candidates = ArchitectureGarbageCollector().candidates(
        architecture=_architecture(),
        registry=registry,
        store={"summary": ()},
    )
    assert candidates and candidates[0].node_id == "summary"


def test_evidence_record_digest_is_stable() -> None:
    row: EvidenceRecord = build_evidence_record("e1", 1, {"value": "oak"})
    assert len(row.digest) == 64
