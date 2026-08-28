from __future__ import annotations

from collections.abc import Iterable

from projects.sem_paper.method.self_evolving_memory.architecture import (
    SemPaperArchitecturePreset,
    architecture_digest,
    architecture_from_dict,
    architecture_to_dict,
    build_sem_paper_architecture,
)
from projects.sem_paper.method.self_evolving_memory.architecture.records import NodePartitionedRecord
from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore, build_evidence_record
from projects.sem_paper.method.self_evolving_memory.typed_builders import (
    TypedSemanticNodeTransformPort,
    build_sem_paper_typed_materialization_configuration,
)
from projects.sem_paper.method.self_evolving_memory.typed_materialization import TypedMemoryMaterializer


def test_current_sem_paper_presets_are_valid_and_round_trip_without_legacy_imports():
    for preset in (SemPaperArchitecturePreset.C, SemPaperArchitecturePreset.X):
        architecture = build_sem_paper_architecture(preset)
        assert architecture.topological_order()
        restored = architecture_from_dict(architecture_to_dict(architecture))
        assert architecture_digest(restored) == architecture_digest(architecture)
        assert restored.architecture_id == preset.value


class _GroundedTransform(TypedSemanticNodeTransformPort):
    def transform(self, *, node, source_records) -> Iterable[NodePartitionedRecord]:
        for index, source in enumerate(source_records):
            payload = dict(source.payload) if isinstance(source.payload, dict) else {}
            refs = (
                (source.evidence_id,)
                if hasattr(source, "evidence_id")
                else (source.record_id,)
            )
            if node.node_id == "mem_world":
                yield NodePartitionedRecord(
                    node.node_id,
                    f"{node.node_id}:{index}",
                    source.sequence,
                    str(payload.get("state_text", "")),
                    {
                        "entity": str(payload["entity"]),
                        "position": payload.get("position"),
                        "state_text": str(payload["state_text"]),
                        "entity_kind": str(payload["entity_kind"]),
                        "observed_at": str(payload["observed_at"]),
                    },
                    refs,
                )
            elif node.node_id == "mem_experience":
                yield NodePartitionedRecord(
                    node.node_id,
                    f"{node.node_id}:{index}",
                    source.sequence,
                    str(payload.get("task", "")),
                    {
                        "task": str(payload["task"]),
                        "context": str(payload["context"]),
                        "action": payload["action"],
                        "outcome": payload["outcome"],
                        "occurred_at": str(payload["occurred_at"]),
                    },
                    refs,
                )
            elif node.node_id == "mem_knowledge":
                yield NodePartitionedRecord(
                    node.node_id,
                    f"{node.node_id}:{index}",
                    source.sequence,
                    str(payload.get("task", "")),
                    {"subject": str(payload["task"]), "rule": "grounded", "confidence": 1.0},
                    refs,
                )
            elif node.node_id == "mem_procedure":
                yield NodePartitionedRecord(
                    node.node_id,
                    f"{node.node_id}:{index}",
                    source.sequence,
                    str(payload.get("task", "")),
                    {"goal": str(payload["task"]), "steps": [payload["action"]], "success_rate": 1.0},
                    refs,
                )


def test_current_builder_routes_only_declared_event_types_and_preserves_jmem_ancestry():
    store = InMemoryEvidenceStore()
    store.append(
        build_evidence_record(
            "world-1",
            1,
            {
                "event_type": "WORLD_OBSERVATION",
                "entity": "entity:tree",
                "position": {"x": 1.0, "y": 2.0, "z": 3.0},
                "state_text": "oak",
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
                "task": "find tree",
                "context": "forest",
                "action": "look",
                "outcome": "verified",
                "occurred_at": "unix_ms:2",
            },
        )
    )
    store.append(build_evidence_record("audit-1", 3, {"event_type": "BRIDGE_AUDIT", "message": "ignored"}))

    config = build_sem_paper_typed_materialization_configuration(_GroundedTransform())
    generation = TypedMemoryMaterializer(store, config.builder).build(
        "g1",
        base_generation="g0",
        candidate_id="current-seed-c",
        architecture=config.architecture,
        contracts=config.contracts,
    )

    records = generation.records
    assert {record.node_id for record in records} == {
        "mem_world",
        "mem_experience",
        "mem_knowledge",
        "mem_procedure",
    }
    assert all("audit-1" not in record.source_refs for record in records)
    assert all(record.source_refs for record in records)
    experience_ids = {
        record.record_id for record in records if record.node_id == "mem_experience"
    }
    assert all(
        set(record.source_refs) <= experience_ids
        for record in records
        if record.node_id in {"mem_knowledge", "mem_procedure"}
    )
    assert generation.deluxe_snapshot().architecture.digest == architecture_digest(config.architecture)
