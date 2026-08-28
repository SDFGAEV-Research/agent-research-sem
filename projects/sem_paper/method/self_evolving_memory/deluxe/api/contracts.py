from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


class MemoryRuntimeTier(StrEnum):
    CORE = "core"
    STANDARD = "standard"
    DELUXE = "deluxe"


@dataclass(frozen=True, slots=True)
class DeluxeNodeDescriptor:
    """Read-only projection of one node in the current method architecture."""

    node_id: str
    purpose: str
    access: tuple[str, ...] = ()
    output_types: tuple[str, ...] = ()
    scope: str = "session"

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.purpose.strip() or not self.scope.strip():
            raise ValueError("Deluxe node identity, purpose and scope are required")
        if any(not value.strip() for value in (*self.access, *self.output_types)):
            raise ValueError("Deluxe node access/output types must be non-empty")
        if len(set(self.access)) != len(self.access) or len(set(self.output_types)) != len(self.output_types):
            raise ValueError("Deluxe node access/output types must be unique")


@dataclass(frozen=True, slots=True)
class DeluxeArchitectureSnapshot:
    """Pinned architecture read model used to derive capabilities.

    The snapshot is not an architecture-head writer. Its digest and generation
    must come from the method's authoritative architecture state.
    """

    generation: str
    digest: str
    nodes: tuple[DeluxeNodeDescriptor, ...]
    generation_number: int = 0

    def __post_init__(self) -> None:
        if not self.generation.strip() or not self.digest.strip():
            raise ValueError("Deluxe architecture generation and digest are required")
        if self.generation_number < 0:
            raise ValueError("Deluxe architecture generation_number must be non-negative")
        node_ids = tuple(node.node_id for node in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Deluxe architecture node ids must be unique")


class CapabilityState(StrEnum):
    PROBATION = "PROBATION"
    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    RETIRE_CANDIDATE = "RETIRE_CANDIDATE"


@dataclass(frozen=True, slots=True)
class CapabilityCard:
    capability_id: str
    provider_node_id: str
    purpose: str
    access: tuple[str, ...]
    output_types: tuple[str, ...]
    scope: str
    generation_created: str

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.capability_id,
                self.provider_node_id,
                self.purpose,
                self.scope,
                self.generation_created,
            )
        ):
            raise ValueError("Deluxe capability identity fields must be non-empty")

    @property
    def semantic_card(self) -> str:
        return " ".join((self.purpose, self.scope, *self.access, *self.output_types))


@dataclass(slots=True)
class CapabilityLifecycle:
    state: CapabilityState = CapabilityState.ACTIVE
    age_queries: int = 0
    selected_queries: int = 0
    useful_queries: int = 0
    last_selected_query: int = -1
    probation_queries_remaining: int = 0
    lease_queries_remaining: int = 0
    utility_ema: float = 0.0

    def usefulness_rate(self) -> float:
        return self.useful_queries / max(1, self.selected_queries)


@dataclass(frozen=True, slots=True)
class CapabilityLifecycleConfig:
    probation_queries: int = 12
    lease_queries: int = 80
    dormant_after_queries: int = 40
    min_probation_selections: int = 2
    min_probation_usefulness: float = 0.20
    retire_after_dormant_queries: int = 80

    def __post_init__(self) -> None:
        if min(
            self.probation_queries,
            self.lease_queries,
            self.dormant_after_queries,
            self.min_probation_selections,
            self.retire_after_dormant_queries,
        ) <= 0:
            raise ValueError("Deluxe capability lifecycle counts must be positive")
        if not 0.0 <= self.min_probation_usefulness <= 1.0:
            raise ValueError("Deluxe probation usefulness must be in [0,1]")


@dataclass(frozen=True, slots=True)
class QueryBudget:
    node_limit: int
    record_limit: int
    token_budget: int
    exploration_slots: int = 0

    def __post_init__(self) -> None:
        if min(self.node_limit, self.record_limit, self.token_budget) <= 0:
            raise ValueError("Deluxe query budgets must be positive")
        if self.exploration_slots < 0 or self.exploration_slots > self.node_limit:
            raise ValueError("Deluxe exploration_slots must fit node_limit")


@dataclass(frozen=True, slots=True)
class BudgetPolicyConfig:
    default_nodes: int = 3
    default_records: int = 8
    default_tokens: int = 1800
    min_nodes: int = 1
    max_nodes: int = 8
    min_records: int = 2
    max_records: int = 24
    exploration_fraction: float = 0.20
    per_node_record_cap: int = 8
    probation_budget_scale: float = 0.60

    def __post_init__(self) -> None:
        if min(self.default_nodes, self.default_records, self.default_tokens, self.min_nodes, self.max_nodes, self.min_records, self.max_records, self.per_node_record_cap) <= 0:
            raise ValueError("Deluxe budget counts must be positive")
        if self.min_nodes > self.max_nodes or self.min_records > self.max_records:
            raise ValueError("Deluxe budget minimum cannot exceed maximum")
        if not 0.0 <= self.exploration_fraction <= 1.0:
            raise ValueError("Deluxe exploration_fraction must be in [0,1]")
        if not 0.0 < self.probation_budget_scale <= 1.0:
            raise ValueError("Deluxe probation_budget_scale must be in (0,1]")


@dataclass(frozen=True, slots=True)
class WorkingSetEntry:
    capability_id: str
    node_id: str
    score: float
    exploration: bool = False


@dataclass(frozen=True, slots=True)
class WorkingSet:
    entries: tuple[WorkingSetEntry, ...]
    budget_nodes: int

    def __post_init__(self) -> None:
        if self.budget_nodes <= 0:
            raise ValueError("Deluxe working-set budget must be positive")
        ids = tuple(entry.capability_id for entry in self.entries)
        if len(ids) != len(set(ids)):
            raise ValueError("Deluxe working set cannot contain duplicate capabilities")
        if len(self.entries) > self.budget_nodes:
            raise ValueError("Deluxe working set exceeds its node budget")

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(entry.node_id for entry in self.entries)

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(entry.capability_id for entry in self.entries)


@dataclass(frozen=True, slots=True)
class WorkingSetPolicyConfig:
    relevance_weight: float = 1.0
    utility_weight: float = 0.20
    reliability_weight: float = 0.15
    cost_weight: float = 0.10
    exploration_bonus: float = 0.05


@dataclass(frozen=True, slots=True)
class MemoryFault:
    fault_id: str
    intent: str
    missing_capability_id: str
    missing_node_id: str
    reason: str
    recovered: bool


@dataclass(frozen=True, slots=True)
class LineageEdge:
    source_ref: str
    derived_ref: str
    relation: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.source_ref, self.derived_ref, self.relation)):
            raise ValueError("Deluxe lineage edge fields must be non-empty")


@dataclass(frozen=True, slots=True)
class MemoryLineageRecord:
    record_id: str
    generation: str
    source_refs: tuple[str, ...] = ()
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.generation.strip():
            raise ValueError("Deluxe lineage record identity is required")
        if any(not value.strip() for value in self.source_refs):
            raise ValueError("Deluxe lineage source refs must be non-empty")


__all__ = [
    "BudgetPolicyConfig",
    "CapabilityCard",
    "CapabilityLifecycle",
    "CapabilityLifecycleConfig",
    "CapabilityState",
    "DeluxeArchitectureSnapshot",
    "DeluxeNodeDescriptor",
    "LineageEdge",
    "MemoryFault",
    "MemoryLineageRecord",
    "MemoryRuntimeTier",
    "QueryBudget",
    "WorkingSet",
    "WorkingSetEntry",
    "WorkingSetPolicyConfig",
]
