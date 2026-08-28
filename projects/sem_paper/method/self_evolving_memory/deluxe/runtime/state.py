from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from ..api import CapabilityCard, CapabilityLifecycle, CapabilityState, MemoryFault
from ...serving import ServingRuntimeState
from .budget import FineGrainedBudgetPolicy
from .capabilities import CapabilityRegistry
from .memory_fault import MemoryFaultHandler
from .working_set import ArchitectureOpenWorkingSetPolicy


STATE_KIND = "sem.deluxe.adaptive_serving"
STATE_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class CapabilityRuntimeState:
    card: CapabilityCard
    state: CapabilityState
    age_queries: int
    selected_queries: int
    useful_queries: int
    last_selected_query: int
    probation_queries_remaining: int
    lease_queries_remaining: int
    utility_ema: float

    def __post_init__(self) -> None:
        counts = (
            self.age_queries,
            self.selected_queries,
            self.useful_queries,
            self.probation_queries_remaining,
            self.lease_queries_remaining,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
            raise ValueError("Deluxe capability runtime counts must be non-negative integers")
        if isinstance(self.last_selected_query, bool) or not isinstance(self.last_selected_query, int) or self.last_selected_query < -1:
            raise ValueError("Deluxe capability last-selected query is invalid")
        if self.useful_queries > self.selected_queries:
            raise ValueError("Deluxe useful query count cannot exceed selected query count")
        if not math.isfinite(float(self.utility_ema)):
            raise ValueError("Deluxe capability utility EMA must be finite")

    @classmethod
    def capture(cls, card: CapabilityCard, lifecycle: CapabilityLifecycle) -> "CapabilityRuntimeState":
        return cls(
            card,
            lifecycle.state,
            lifecycle.age_queries,
            lifecycle.selected_queries,
            lifecycle.useful_queries,
            lifecycle.last_selected_query,
            lifecycle.probation_queries_remaining,
            lifecycle.lease_queries_remaining,
            lifecycle.utility_ema,
        )

    def materialize_lifecycle(self) -> CapabilityLifecycle:
        return CapabilityLifecycle(
            state=self.state,
            age_queries=self.age_queries,
            selected_queries=self.selected_queries,
            useful_queries=self.useful_queries,
            last_selected_query=self.last_selected_query,
            probation_queries_remaining=self.probation_queries_remaining,
            lease_queries_remaining=self.lease_queries_remaining,
            utility_ema=self.utility_ema,
        )


@dataclass(frozen=True, slots=True)
class DeluxeServingRuntimeState:
    query_clock: int
    architecture_generation: str | None
    architecture_digest: str | None
    capabilities: tuple[CapabilityRuntimeState, ...]
    budget_node_costs: tuple[tuple[str, float], ...]
    budget_capability_costs: tuple[tuple[str, float], ...]
    working_set_utility: tuple[tuple[str, float], ...]
    working_set_reliability: tuple[tuple[str, float], ...]
    working_set_cost: tuple[tuple[str, float], ...]
    faults: tuple[MemoryFault, ...]
    unresolved_rate: float
    cost_pressure: float

    def __post_init__(self) -> None:
        if isinstance(self.query_clock, bool) or not isinstance(self.query_clock, int) or self.query_clock < 0:
            raise ValueError("Deluxe serving query clock must be a non-negative integer")
        if (self.architecture_generation is None) != (self.architecture_digest is None):
            raise ValueError("Deluxe architecture generation/digest must be present together")
        if self.architecture_generation is not None and (
            not self.architecture_generation.strip() or not self.architecture_digest or not self.architecture_digest.strip()
        ):
            raise ValueError("Deluxe architecture state identity cannot be empty")
        ids = tuple(row.card.capability_id for row in self.capabilities)
        if len(ids) != len(set(ids)):
            raise ValueError("Deluxe serving state contains duplicate capabilities")
        for name, pairs in (
            ("budget node costs", self.budget_node_costs),
            ("budget capability costs", self.budget_capability_costs),
            ("working-set utility", self.working_set_utility),
            ("working-set reliability", self.working_set_reliability),
            ("working-set cost", self.working_set_cost),
        ):
            keys = tuple(key for key, _ in pairs)
            if len(keys) != len(set(keys)) or any(not key.strip() for key in keys):
                raise ValueError(f"Deluxe {name} contains invalid keys")
            if any(not math.isfinite(float(value)) for _, value in pairs):
                raise ValueError(f"Deluxe {name} must contain finite values")
        if any(value < 0.0 for _, value in (*self.budget_node_costs, *self.budget_capability_costs, *self.working_set_cost)):
            raise ValueError("Deluxe cost state cannot be negative")
        if any(not 0.0 <= value <= 1.0 for _, value in self.working_set_reliability):
            raise ValueError("Deluxe working-set reliability must be in [0,1]")
        if not math.isfinite(float(self.unresolved_rate)) or self.unresolved_rate < 0.0:
            raise ValueError("Deluxe unresolved rate must be finite and non-negative")
        if not math.isfinite(float(self.cost_pressure)) or self.cost_pressure < 0.0:
            raise ValueError("Deluxe cost pressure must be finite and non-negative")
        fault_ids = tuple(fault.fault_id for fault in self.faults)
        if len(fault_ids) != len(set(fault_ids)):
            raise ValueError("Deluxe serving state contains duplicate fault ids")


def _pairs(mapping: Mapping[str, float]) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((str(key), float(value)) for key, value in mapping.items()))


def capture_deluxe_serving_state(
    registry: CapabilityRegistry,
    budget: FineGrainedBudgetPolicy,
    working_set: ArchitectureOpenWorkingSetPolicy,
    faults: MemoryFaultHandler,
    *,
    unresolved_rate: float,
    cost_pressure: float,
) -> ServingRuntimeState:
    state = DeluxeServingRuntimeState(
        query_clock=registry.query_clock,
        architecture_generation=registry.architecture_generation,
        architecture_digest=registry.architecture_digest,
        capabilities=tuple(
            CapabilityRuntimeState.capture(registry.cards[capability_id], registry.lifecycle[capability_id])
            for capability_id in sorted(registry.cards)
        ),
        budget_node_costs=_pairs(budget.node_cost_ema),
        budget_capability_costs=_pairs(budget.capability_cost_ema),
        working_set_utility=_pairs(working_set.provider_utility),
        working_set_reliability=_pairs(working_set.provider_reliability),
        working_set_cost=_pairs(working_set.provider_cost),
        faults=tuple(faults.faults),
        unresolved_rate=float(unresolved_rate),
        cost_pressure=float(cost_pressure),
    )
    payload = {
        "query_clock": state.query_clock,
        "architecture_generation": state.architecture_generation,
        "architecture_digest": state.architecture_digest,
        "capabilities": [
            {
                "card": {
                    "capability_id": row.card.capability_id,
                    "provider_node_id": row.card.provider_node_id,
                    "purpose": row.card.purpose,
                    "access": list(row.card.access),
                    "output_types": list(row.card.output_types),
                    "scope": row.card.scope,
                    "generation_created": row.card.generation_created,
                },
                "lifecycle": {
                    "state": row.state.value,
                    "age_queries": row.age_queries,
                    "selected_queries": row.selected_queries,
                    "useful_queries": row.useful_queries,
                    "last_selected_query": row.last_selected_query,
                    "probation_queries_remaining": row.probation_queries_remaining,
                    "lease_queries_remaining": row.lease_queries_remaining,
                    "utility_ema": row.utility_ema,
                },
            }
            for row in state.capabilities
        ],
        "budget_node_costs": dict(state.budget_node_costs),
        "budget_capability_costs": dict(state.budget_capability_costs),
        "working_set_utility": dict(state.working_set_utility),
        "working_set_reliability": dict(state.working_set_reliability),
        "working_set_cost": dict(state.working_set_cost),
        "faults": [
            {
                "fault_id": fault.fault_id,
                "intent": fault.intent,
                "missing_capability_id": fault.missing_capability_id,
                "missing_node_id": fault.missing_node_id,
                "reason": fault.reason,
                "recovered": fault.recovered,
            }
            for fault in state.faults
        ],
        "unresolved_rate": state.unresolved_rate,
        "cost_pressure": state.cost_pressure,
    }
    return ServingRuntimeState(STATE_KIND, STATE_SCHEMA_VERSION, payload)


def _require_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"Deluxe serving state {label} must be an object")
    return value


def _decode_float_map(value: object, label: str) -> tuple[tuple[str, float], ...]:
    mapping = _require_object(value, label)
    result: list[tuple[str, float]] = []
    for key, raw in mapping.items():
        if not isinstance(key, str) or not key.strip() or isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"Deluxe serving state {label} entry is invalid")
        result.append((key, float(raw)))
    return tuple(sorted(result))


def decode_deluxe_serving_state(snapshot: ServingRuntimeState) -> DeluxeServingRuntimeState:
    if snapshot.state_kind != STATE_KIND or snapshot.schema_version != STATE_SCHEMA_VERSION:
        raise ValueError("Deluxe serving checkpoint identity mismatch")
    payload = _require_object(snapshot.payload, "payload")
    expected = {
        "query_clock", "architecture_generation", "architecture_digest", "capabilities",
        "budget_node_costs", "budget_capability_costs", "working_set_utility",
        "working_set_reliability", "working_set_cost", "faults", "unresolved_rate", "cost_pressure",
    }
    if set(payload) != expected:
        raise ValueError("Deluxe serving checkpoint fields are not exact")
    query_clock = payload["query_clock"]
    if isinstance(query_clock, bool) or not isinstance(query_clock, int):
        raise ValueError("Deluxe serving checkpoint query_clock must be an integer")
    generation = payload["architecture_generation"]
    digest = payload["architecture_digest"]
    if generation is not None and not isinstance(generation, str):
        raise ValueError("Deluxe serving checkpoint architecture_generation is invalid")
    if digest is not None and not isinstance(digest, str):
        raise ValueError("Deluxe serving checkpoint architecture_digest is invalid")
    raw_capabilities = payload["capabilities"]
    if not isinstance(raw_capabilities, (list, tuple)):
        raise ValueError("Deluxe serving checkpoint capabilities must be a sequence")
    capabilities: list[CapabilityRuntimeState] = []
    card_fields = {"capability_id", "provider_node_id", "purpose", "access", "output_types", "scope", "generation_created"}
    lifecycle_fields = {
        "state", "age_queries", "selected_queries", "useful_queries", "last_selected_query",
        "probation_queries_remaining", "lease_queries_remaining", "utility_ema",
    }
    for item in raw_capabilities:
        row = _require_object(item, "capability")
        if set(row) != {"card", "lifecycle"}:
            raise ValueError("Deluxe capability checkpoint fields are not exact")
        card_row = _require_object(row["card"], "capability card")
        life_row = _require_object(row["lifecycle"], "capability lifecycle")
        if set(card_row) != card_fields or set(life_row) != lifecycle_fields:
            raise ValueError("Deluxe capability checkpoint schema mismatch")
        access = card_row["access"]
        output_types = card_row["output_types"]
        if not isinstance(access, (list, tuple)) or not isinstance(output_types, (list, tuple)):
            raise ValueError("Deluxe capability access/output types must be sequences")
        card = CapabilityCard(
            capability_id=str(card_row["capability_id"]),
            provider_node_id=str(card_row["provider_node_id"]),
            purpose=str(card_row["purpose"]),
            access=tuple(str(value) for value in access),
            output_types=tuple(str(value) for value in output_types),
            scope=str(card_row["scope"]),
            generation_created=str(card_row["generation_created"]),
        )
        int_names = (
            "age_queries", "selected_queries", "useful_queries", "last_selected_query",
            "probation_queries_remaining", "lease_queries_remaining",
        )
        if any(isinstance(life_row[name], bool) or not isinstance(life_row[name], int) for name in int_names):
            raise ValueError("Deluxe capability lifecycle counts must be integers")
        utility_ema = life_row["utility_ema"]
        if isinstance(utility_ema, bool) or not isinstance(utility_ema, (int, float)):
            raise ValueError("Deluxe capability utility EMA must be numeric")
        capabilities.append(CapabilityRuntimeState(
            card=card,
            state=CapabilityState(str(life_row["state"])),
            age_queries=int(life_row["age_queries"]),
            selected_queries=int(life_row["selected_queries"]),
            useful_queries=int(life_row["useful_queries"]),
            last_selected_query=int(life_row["last_selected_query"]),
            probation_queries_remaining=int(life_row["probation_queries_remaining"]),
            lease_queries_remaining=int(life_row["lease_queries_remaining"]),
            utility_ema=float(utility_ema),
        ))
    raw_faults = payload["faults"]
    if not isinstance(raw_faults, (list, tuple)):
        raise ValueError("Deluxe serving checkpoint faults must be a sequence")
    fault_fields = {"fault_id", "intent", "missing_capability_id", "missing_node_id", "reason", "recovered"}
    faults: list[MemoryFault] = []
    for item in raw_faults:
        row = _require_object(item, "fault")
        if set(row) != fault_fields or not isinstance(row["recovered"], bool):
            raise ValueError("Deluxe fault checkpoint schema mismatch")
        faults.append(MemoryFault(
            str(row["fault_id"]), str(row["intent"]), str(row["missing_capability_id"]),
            str(row["missing_node_id"]), str(row["reason"]), row["recovered"],
        ))
    unresolved = payload["unresolved_rate"]
    pressure = payload["cost_pressure"]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (unresolved, pressure)):
        raise ValueError("Deluxe serving adaptive rates must be numeric")
    return DeluxeServingRuntimeState(
        query_clock=query_clock,
        architecture_generation=generation,
        architecture_digest=digest,
        capabilities=tuple(capabilities),
        budget_node_costs=_decode_float_map(payload["budget_node_costs"], "budget_node_costs"),
        budget_capability_costs=_decode_float_map(payload["budget_capability_costs"], "budget_capability_costs"),
        working_set_utility=_decode_float_map(payload["working_set_utility"], "working_set_utility"),
        working_set_reliability=_decode_float_map(payload["working_set_reliability"], "working_set_reliability"),
        working_set_cost=_decode_float_map(payload["working_set_cost"], "working_set_cost"),
        faults=tuple(faults),
        unresolved_rate=float(unresolved),
        cost_pressure=float(pressure),
    )


def restore_deluxe_serving_state(
    snapshot: ServingRuntimeState,
    registry: CapabilityRegistry,
    budget: FineGrainedBudgetPolicy,
    working_set: ArchitectureOpenWorkingSetPolicy,
    faults: MemoryFaultHandler,
) -> DeluxeServingRuntimeState:
    state = decode_deluxe_serving_state(snapshot)
    registry.query_clock = state.query_clock
    registry.architecture_generation = state.architecture_generation
    registry.architecture_digest = state.architecture_digest
    registry.cards = {row.card.capability_id: row.card for row in state.capabilities}
    registry.lifecycle = {row.card.capability_id: row.materialize_lifecycle() for row in state.capabilities}
    budget.node_cost_ema = dict(state.budget_node_costs)
    budget.capability_cost_ema = dict(state.budget_capability_costs)
    working_set.provider_utility = dict(state.working_set_utility)
    working_set.provider_reliability = dict(state.working_set_reliability)
    working_set.provider_cost = dict(state.working_set_cost)
    faults.faults = list(state.faults)
    return state


__all__ = [
    "CapabilityRuntimeState",
    "DeluxeServingRuntimeState",
    "STATE_KIND",
    "STATE_SCHEMA_VERSION",
    "capture_deluxe_serving_state",
    "decode_deluxe_serving_state",
    "restore_deluxe_serving_state",
]
