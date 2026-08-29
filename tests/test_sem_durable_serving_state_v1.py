from __future__ import annotations

import json
from copy import deepcopy
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


@pytest.mark.parametrize(
    "case",
    (
        "capability_id_number", "access_number", "access_tuple", "state_boolean",
        "count_boolean", "utility_overflow", "float_map_string", "float_map_overflow",
        "fault_text_number", "fault_recovered_number", "adaptive_rate_string",
        "adaptive_rate_overflow", "capabilities_tuple", "empty_architecture_generation",
    ),
)
def test_deluxe_serving_state_rejects_coercive_or_overflowing_documents(case: str) -> None:
    service = _service()
    service.recall("oak tree", limit=2)
    before = service.snapshot_state()
    payload = deepcopy(dict(before.payload))
    capability = payload["capabilities"][0]
    if case == "capability_id_number": capability["card"]["capability_id"] = 7
    elif case == "access_number": capability["card"]["access"][0] = 7
    elif case == "access_tuple": capability["card"]["access"] = tuple(capability["card"]["access"])
    elif case == "state_boolean": capability["lifecycle"]["state"] = True
    elif case == "count_boolean": capability["lifecycle"]["age_queries"] = True
    elif case == "utility_overflow": capability["lifecycle"]["utility_ema"] = 10**10000
    elif case == "float_map_string": payload["working_set_utility"]["cap_deadbeef"] = "1.5"
    elif case == "float_map_overflow": payload["working_set_utility"]["cap_deadbeef"] = 10**10000
    elif case in {"fault_text_number", "fault_recovered_number"}:
        payload["faults"] = [{
            "fault_id": "mf_test", "intent": (7 if case == "fault_text_number" else "intent"),
            "missing_capability_id": "cap_test", "missing_node_id": "node_test",
            "reason": "test_reason", "recovered": (1 if case == "fault_recovered_number" else True),
        }]
    elif case == "adaptive_rate_string": payload["unresolved_rate"] = "0.5"
    elif case == "adaptive_rate_overflow": payload["cost_pressure"] = 10**10000
    elif case == "capabilities_tuple": payload["capabilities"] = tuple(payload["capabilities"])
    elif case == "empty_architecture_generation": payload["architecture_generation"] = ""
    malformed = ServingRuntimeState(before.state_kind, before.schema_version, payload)
    with pytest.raises(ValueError):
        service.validate_state(malformed)
    assert service.snapshot_state() == before


@pytest.mark.parametrize(
    "case",
    (
        "map_key_number", "map_value_string", "map_value_boolean", "map_value_overflow",
        "unresolved_rate_string", "cost_pressure_boolean", "lifecycle_ema_string",
        "lifecycle_state_string", "capability_access_number", "architecture_generation_number",
    ),
)
def test_deluxe_serving_snapshot_rejects_corrupt_runtime_state(case: str) -> None:
    service = _service()
    service.recall("oak tree", limit=2)
    capability_id = next(iter(service.registry.cards))
    if case == "map_key_number": service.budget_policy.node_cost_ema[7] = 1.0  # type: ignore[index]
    elif case == "map_value_string": service.budget_policy.node_cost_ema["events"] = "1.5"  # type: ignore[assignment]
    elif case == "map_value_boolean": service.budget_policy.node_cost_ema["events"] = True  # type: ignore[assignment]
    elif case == "map_value_overflow": service.budget_policy.node_cost_ema["events"] = 10**10000
    elif case == "unresolved_rate_string": service.unresolved_rate = "0.5"  # type: ignore[assignment]
    elif case == "cost_pressure_boolean": service.cost_pressure = True  # type: ignore[assignment]
    elif case == "lifecycle_ema_string": service.registry.lifecycle[capability_id].utility_ema = "0.5"  # type: ignore[assignment]
    elif case == "lifecycle_state_string": service.registry.lifecycle[capability_id].state = "ACTIVE"  # type: ignore[assignment]
    elif case == "capability_access_number":
        service.registry.cards[capability_id] = replace(service.registry.cards[capability_id], access=(7,))  # type: ignore[arg-type]
    elif case == "architecture_generation_number": service.registry.architecture_generation = 7  # type: ignore[assignment]
    with pytest.raises(ValueError):
        service.snapshot_state()
