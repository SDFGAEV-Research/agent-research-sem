from __future__ import annotations

from projects.sem_paper.composition import build_seed_x_candidate
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
                "outcome": {"verified": True},
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
