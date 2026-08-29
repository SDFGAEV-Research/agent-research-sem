from __future__ import annotations

import pytest

from projects.sem_paper.composition import build_seed_x_candidate
from projects.sem_paper.method.self_evolving_memory.architecture import (
    SemPaperArchitecturePreset,
    build_sem_paper_architecture,
)
from projects.sem_paper.method.self_evolving_memory.evidence_memory import (
    InMemoryEvidenceStore,
    build_evidence_record,
)
from projects.sem_paper.method.self_evolving_memory.minecraft_transform import (
    MinecraftGroundedSemanticTransformer,
)
from projects.sem_paper.method.self_evolving_memory.typed_builders import (
    build_sem_paper_typed_materialization_configuration,
)
from projects.sem_paper.method.self_evolving_memory.typed_materialization import (
    TypedMemoryMaterializer,
)


def test_minecraft_candidate_materializes_seed_x_from_jmem_with_ancestry() -> None:
    store = InMemoryEvidenceStore()
    store.append(
        build_evidence_record(
            "world-1",
            1,
            {
                "event_type": "WORLD_OBSERVATION",
                "entity": "entity:oak",
                "position": {"x": 1.0, "y": 64.0, "z": 2.0},
                "state_text": "oak log",
                "entity_kind": "BLOCK",
                "observed_at": "unix_ms:1",
            },
        )
    )
    store.append(
        build_evidence_record(
            "action-1",
            2,
            {
                "event_type": "ACTION_RESULT",
                "task": "gather logs",
                "context": "forest",
                "action": {"tool": "dig", "target": "oak_log"},
                "outcome": {"status": "applied"},
                "verified": True,
                "occurred_at": "unix_ms:2",
            },
        )
    )

    candidate = build_seed_x_candidate()
    configuration = build_sem_paper_typed_materialization_configuration(
        MinecraftGroundedSemanticTransformer(),
        preset=candidate.target_spec.architecture_id,
    )
    generation = TypedMemoryMaterializer(store, configuration.builder).build(
        "g1",
        base_generation=candidate.base_generation,
        candidate_id=candidate.candidate_id,
        architecture=configuration.architecture,
        contracts=configuration.contracts,
    )

    assert configuration.architecture == candidate.target_spec
    assert {record.node_id for record in generation.records} == {
        "mem_spatial",
        "mem_entity",
        "mem_event",
        "mem_pattern",
    }
    assert all(record.source_refs for record in generation.records)
    assert any(record.node_id == "mem_pattern" for record in generation.records)


def test_grounded_action_result_rejects_missing_or_unverified_scientific_facts() -> None:
    node = build_sem_paper_architecture(SemPaperArchitecturePreset.C).get("mem_experience")
    transformer = MinecraftGroundedSemanticTransformer()
    base = {
        "event_type": "ACTION_RESULT",
        "task": "gather logs",
        "context": "forest",
        "action": {"tool": "dig", "target": "oak_log"},
        "outcome": {"status": "applied"},
        "verified": True,
        "occurred_at": "unix_ms:2",
    }
    for mutation, message in (
        ({"task": ""}, "task"),
        ({"action": None}, "action"),
        ({"outcome": "applied"}, "outcome"),
        ({"verified": False}, "unverified"),
        ({"verified": "true"}, "verified"),
    ):
        payload = {**base, **mutation}
        row = build_evidence_record("action", 1, payload)
        with pytest.raises(ValueError, match=message):
            tuple(transformer.transform(node=node, source_records=(row,)))


def test_procedure_success_rate_uses_action_outcome_not_evidence_verification() -> None:
    architecture = build_sem_paper_architecture(SemPaperArchitecturePreset.C)
    transformer = MinecraftGroundedSemanticTransformer()
    action_row = build_evidence_record(
        "action-rejected",
        1,
        {
            "event_type": "ACTION_RESULT",
            "task": "craft tool",
            "context": "bench",
            "action": {"tool": "craft_item", "item": "pickaxe"},
            "outcome": {"status": "rejected", "code": "NO_RECIPE"},
            "verified": True,
            "occurred_at": "unix_ms:3",
        },
    )
    experience = tuple(
        transformer.transform(
            node=architecture.get("mem_experience"),
            source_records=(action_row,),
        )
    )
    procedure = tuple(
        transformer.transform(
            node=architecture.get("mem_procedure"),
            source_records=experience,
        )
    )
    assert len(procedure) == 1
    assert procedure[0].payload["success_rate"] == 0.0
    assert procedure[0].payload["steps"] == [{"tool": "craft_item", "item": "pickaxe"}]
