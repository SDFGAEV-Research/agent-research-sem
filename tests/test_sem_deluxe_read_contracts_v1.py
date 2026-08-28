from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from projects.sem_paper.method.self_evolving_memory.authority import validate_tier_authority
from projects.sem_paper.method.self_evolving_memory.deluxe.api import (
    DeluxeArchitectureSnapshot,
    DeluxeNodeDescriptor,
    CapabilityState,
    MemoryRuntimeTier,
    MemoryLineageRecord,
)
from projects.sem_paper.method.self_evolving_memory.deluxe.runtime import (
    ArchitectureOpenWorkingSetPolicy,
    CapabilityRegistry,
    DeluxeMemoryServingService,
    DeluxeGroundingAudit,
    FineGrainedBudgetPolicy,
    MemoryFaultHandler,
    MemoryLineageGraph,
    audit_deluxe_grounding,
)


@dataclass(frozen=True, slots=True)
class _Record:
    node_id: str
    record_id: str
    sequence: int
    text: str
    payload: Mapping[str, object]
    source_refs: tuple[str, ...] = ()


class _DeluxeSource:
    def __init__(self, architecture, records):
        self._architecture = architecture
        self._records = records

    def open_deluxe_snapshot(self):
        return self

    @property
    def generation(self):
        return self._architecture.generation

    @property
    def architecture(self):
        return self._architecture

    def node_ids(self):
        return tuple(self._records)

    def iter_records(self, node_id):
        return iter(self._records.get(node_id, ()))


def _architecture() -> DeluxeArchitectureSnapshot:
    return DeluxeArchitectureSnapshot(
        generation="g1",
        digest="a" * 64,
        generation_number=1,
        nodes=(
            DeluxeNodeDescriptor("semantic", "semantic task evidence", ("semantic",), ("text",)),
            DeluxeNodeDescriptor("action", "action outcome evidence", ("action",), ("outcome",)),
            DeluxeNodeDescriptor("fresh", "fresh task evidence", ("semantic",), ("text",)),
        ),
    )


def test_deluxe_read_contracts_are_architecture_derived_and_authority_neutral() -> None:
    validate_tier_authority()
    assert MemoryRuntimeTier.CORE.value == "core"
    registry = CapabilityRegistry()
    registry.sync_architecture(_architecture())
    assert registry.architecture_generation == "g1"
    assert registry.architecture_digest == "a" * 64
    assert len(registry.cards) == 3
    assert all(lifecycle.state is CapabilityState.PROBATION for lifecycle in registry.lifecycle.values())

    ranked = registry.discover("semantic task")
    assert ranked[0][1].provider_node_id in {"semantic", "fresh"}
    disclosed = registry.disclosed_cards("semantic task", limit=2)
    assert len(disclosed) == 2


def test_deluxe_budget_working_set_and_one_fault_recovery_are_bounded() -> None:
    registry = CapabilityRegistry()
    registry.sync_architecture(_architecture())
    ranked = registry.discover("semantic task")
    budget = FineGrainedBudgetPolicy().allocate(
        requested_nodes=2,
        requested_records=8,
        node_count=len(registry.cards),
        unresolved_rate=0.8,
    )
    working = ArchitectureOpenWorkingSetPolicy(registry).select(
        ranked,
        budget_nodes=budget.node_limit,
        exploration_slots=budget.exploration_slots,
    )
    assert len(working.entries) <= budget.node_limit
    fault_handler = MemoryFaultHandler(registry)
    recovered = fault_handler.recover_if_needed(
        intent="semantic task",
        working_set=working,
        ranked_capabilities=ranked,
        hard_limit=budget.node_limit,
    )
    assert len(recovered.entries) <= budget.node_limit
    assert len(fault_handler.faults) <= 1
    assert 0.0 <= fault_handler.recovery_rate() <= 1.0


def test_deluxe_lineage_is_rebuildable_and_does_not_become_jmem_authority() -> None:
    graph = MemoryLineageGraph()
    graph.rebuild(
        {
            "session": (
                MemoryLineageRecord("memory-2", "g1", ("evidence-1",)),
                MemoryLineageRecord("memory-3", "g1", ("memory-2",)),
            )
        }
    )
    assert [(edge.source_ref, edge.derived_ref) for edge in graph.edges()] == [
        ("evidence-1", "memory-2"),
        ("memory-2", "memory-3"),
    ]
    assert graph.snapshot()["edges"]


def test_deluxe_serving_requires_pinned_node_projection_and_records_diagnostics() -> None:
    architecture = _architecture()
    source = _DeluxeSource(
        architecture,
        {
            "semantic": (_Record("semantic", "m1", 1, "semantic task in overworld", {"text": "semantic task in overworld"}),),
            "action": (_Record("action", "m2", 2, "action outcome collected", {"text": "action outcome collected"}),),
            "fresh": (_Record("fresh", "m3", 3, "fresh semantic task", {"text": "fresh semantic task"}),),
        },
    )
    result = DeluxeMemoryServingService(source).recall("semantic task", limit=2)
    assert result.generation == "g1"
    assert result.selected_nodes
    assert "semantic" in result.context_text or "fresh" in result.context_text
    assert result.diagnostics.tier is MemoryRuntimeTier.DELUXE
    assert result.diagnostics.architecture_digest == "a" * 64


def test_deluxe_serving_rejects_records_outside_the_pinned_architecture() -> None:
    architecture = _architecture()
    source = _DeluxeSource(
        architecture,
        {"unknown": (_Record("unknown", "m1", 1, "unknown", {"text": "unknown"}),)},
    )
    try:
        DeluxeMemoryServingService(source).recall("unknown", limit=1)
    except ValueError as exc:
        assert "outside pinned architecture" in str(exc)
    else:
        raise AssertionError("Deluxe serving accepted an unpinned node")


def test_deluxe_grounding_audit_traces_query_and_materialization_to_jmem() -> None:
    architecture = _architecture()
    source = _DeluxeSource(
        architecture,
        {
            "semantic": (
                _Record("semantic", "m1", 1, "semantic task", {"text": "semantic task"}, ("e1",)),
            ),
            "action": (
                _Record("action", "m2", 2, "action outcome", {"text": "action outcome"}, ("m1",)),
            ),
            "fresh": (
                _Record("fresh", "m3", 3, "fresh semantic", {"text": "fresh semantic"}, ("e2",)),
            ),
        },
    )

    result = DeluxeMemoryServingService(source).recall("semantic task", limit=2)
    audit = audit_deluxe_grounding(
        source,
        result,
        memory_evidence_ids=("e1", "e2"),
    )

    assert isinstance(audit, DeluxeGroundingAudit)
    assert audit.ok is True
    assert audit.query_refs_nonempty is True
    assert audit.query_refs_memory_only is True
    assert audit.materialized_refs_memory_only is True
    assert audit.audit_materialization_leak_count == 0


def test_deluxe_grounding_audit_rejects_audit_and_unknown_ancestry() -> None:
    architecture = _architecture()
    source = _DeluxeSource(
        architecture,
        {
            "semantic": (
                _Record("semantic", "m1", 1, "semantic task", {"text": "semantic task"}, ("audit-1",)),
            ),
            "action": (
                _Record("action", "m2", 2, "action outcome", {"text": "action outcome"}, ("unknown-1",)),
            ),
            "fresh": (),
        },
    )

    result = DeluxeMemoryServingService(source).recall("semantic task", limit=2)
    audit = audit_deluxe_grounding(
        source,
        result,
        memory_evidence_ids=("e1",),
        audit_evidence_ids=("audit-1",),
    )

    assert audit.ok is False
    assert audit.audit_materialization_leak_count == 1
    assert audit.unknown_source_ref_count >= 1
    assert audit.materialized_refs_memory_only is False
