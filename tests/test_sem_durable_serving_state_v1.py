from __future__ import annotations

import json
from dataclasses import replace

import pytest

from sem_test_support import build_fixed_memory_method
from research_platform.participant.method.api import MethodServices, RecallRequest
from research_platform.participant.method.runtime import InMemoryMethodObservationSink
from research_platform.platform.kernel import ExecutionContext

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
    TransformOpSpec,
    TransformPlan,
    TypeSpec,
)
from projects.sem_paper.method.self_evolving_memory.architecture.records import NodePartitionedRecord
from projects.sem_paper.method.self_evolving_memory.deluxe.runtime.serving import DeluxeMemoryServingService
from projects.sem_paper.method.self_evolving_memory.serving import ServingRuntimeState
from projects.sem_paper.method.self_evolving_memory.serving_providers import build_deluxe_session_serving
from projects.sem_paper.method.self_evolving_memory.typed_materialization import (
    TypedMaterializedGeneration,
    build_adopted_typed_snapshot_factory,
)
from projects.sem_paper.method.self_evolving_memory.architecture.projection import NodePartitionedDeluxeSource


def _architecture() -> MemoryArchitectureSpec:
    nodes = tuple(
        MemoryNodeSpec(
            node_id=node_id,
            label=node_id.title(),
            purpose=purpose,
            scope=MemoryScope.AGENT,
            mode=MemoryMode.APPEND,
            schema=(FieldSpec("text", TypeSpec(PrimitiveType.TEXT)),),
            primary_key=(),
            access=frozenset({AccessMode.SEMANTIC}),
            sources=(SourceSpec(SourceKind.EVIDENCE),),
            transform=TransformPlan((TransformOpSpec(OperatorKind.SEMANTIC_MAP),)),
        )
        for node_id, purpose in (
            ("events", "grounded event history"),
            ("plans", "action planning evidence"),
            ("facts", "stable world facts"),
        )
    )
    return MemoryArchitectureSpec("1", "serving-state-test", 1, nodes)


def _generation() -> TypedMaterializedGeneration:
    architecture = _architecture()
    records = (
        NodePartitionedRecord("events", "events:1", 1, "oak tree observed", {"text": "oak tree observed"}, ("e1",)),
        NodePartitionedRecord("plans", "plans:1", 2, "craft wooden pickaxe", {"text": "craft wooden pickaxe"}, ("e2",)),
        NodePartitionedRecord("facts", "facts:1", 3, "cave contains stone", {"text": "cave contains stone"}, ("e3",)),
    )
    return TypedMaterializedGeneration("g0", "g0", "candidate", architecture, 3, "a" * 64, records)


def _service() -> DeluxeMemoryServingService:
    return DeluxeMemoryServingService(NodePartitionedDeluxeSource(_generation().deluxe_snapshot()))


def test_deluxe_adaptive_serving_state_round_trips_exact_next_recall() -> None:
    source = _service()
    for intent in ("oak tree", "craft pickaxe", "oak tree", "stone cave", "oak tree"):
        source.recall(intent, limit=2)
    checkpoint = source.snapshot_state()

    expected = source.recall("craft pickaxe", limit=2)
    expected_after = source.snapshot_state()

    resumed = _service()
    resumed.validate_state(checkpoint)
    resumed.restore_state(checkpoint)
    actual = resumed.recall("craft pickaxe", limit=2)

    assert actual.selected_nodes == expected.selected_nodes
    assert actual.selected_record_ids == expected.selected_record_ids
    assert actual.context_text == expected.context_text
    assert resumed.snapshot_state() == expected_after


def test_deluxe_serving_state_validation_is_fail_closed_and_non_mutating() -> None:
    service = _service()
    service.recall("oak tree", limit=2)
    before = service.snapshot_state()
    payload = dict(before.payload)
    payload["unexpected"] = True
    malformed = ServingRuntimeState(before.state_kind, before.schema_version, payload)

    with pytest.raises(ValueError, match="fields are not exact"):
        service.validate_state(malformed)
    assert service.snapshot_state() == before

    wrong = replace(before, schema_version="999")
    with pytest.raises(ValueError, match="identity mismatch"):
        service.restore_state(wrong)
    assert service.snapshot_state() == before


def test_method_checkpoint_embeds_and_restores_deluxe_serving_state() -> None:
    generation = _generation()
    method = build_fixed_memory_method(
        serving_factory=build_deluxe_session_serving,
        serving_provider_id="deluxe.checkpoint.test.v1",
        deluxe_snapshot_factory=build_adopted_typed_snapshot_factory(generation),
    )
    services = MethodServices(InMemoryMethodObservationSink())
    context = ExecutionContext("run", "trace", "span", task_id="task", decision_cycle_id="dc")
    source = method.open_session(session_id="session", services=services)
    source.recall(RecallRequest("oak tree", context, 2))
    source.recall(RecallRequest("stone cave", context, 2))
    checkpoint = source.checkpoint()
    document = json.loads(checkpoint.opaque_payload)
    assert document["serving_state"]["state_kind"] == "sem.deluxe.adaptive_serving"
    assert document["serving_state"]["payload"]["query_clock"] == 2

    target = method.open_session(session_id="session", services=MethodServices(InMemoryMethodObservationSink()))
    target.restore(checkpoint)
    restored = json.loads(target.checkpoint().opaque_payload)
    assert restored["serving_state"] == document["serving_state"]


def test_core_serving_checkpoint_is_explicitly_stateless() -> None:
    method = build_fixed_memory_method()
    session = method.open_session(
        session_id="core",
        services=MethodServices(InMemoryMethodObservationSink()),
    )
    document = json.loads(session.checkpoint().opaque_payload)
    assert document["serving_state"] == {
        "state_kind": "sem.memory_serving.stateless",
        "schema_version": "1",
        "payload": {},
    }
