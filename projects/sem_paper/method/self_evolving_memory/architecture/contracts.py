from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import Any, Mapping


class PrimitiveType(StrEnum):
    TEXT = "TEXT"
    CATEGORY = "CATEGORY"
    BOOL = "BOOL"
    INT = "INT"
    FLOAT = "FLOAT"
    ENTITY = "ENTITY"
    POSITION = "POSITION"
    TIME = "TIME"
    ACTION = "ACTION"
    OUTCOME = "OUTCOME"
    EVIDENCE_REF = "EVIDENCE_REF"
    MEMORY_REF = "MEMORY_REF"


class ContainerKind(StrEnum):
    SCALAR = "SCALAR"
    OPTIONAL = "OPTIONAL"
    LIST = "LIST"
    SET = "SET"


class MemoryScope(StrEnum):
    WORLD = "WORLD"
    AGENT = "AGENT"


class MemoryMode(StrEnum):
    APPEND = "APPEND"
    CURRENT = "CURRENT"
    AGGREGATE = "AGGREGATE"


class AccessMode(StrEnum):
    SEMANTIC = "SEMANTIC"
    ENTITY = "ENTITY"
    SPATIAL = "SPATIAL"
    TEMPORAL = "TEMPORAL"
    EXACT = "EXACT"


class OperatorKind(StrEnum):
    FILTER = "FILTER"
    PROJECT = "PROJECT"
    GROUP_BY = "GROUP_BY"
    DEDUP = "DEDUP"
    UNION = "UNION"
    AGGREGATE_STATS = "AGGREGATE_STATS"
    SEMANTIC_MAP = "SEMANTIC_MAP"
    SEMANTIC_REDUCE = "SEMANTIC_REDUCE"
    SEMANTIC_COMPOSE = "SEMANTIC_COMPOSE"


class SourceKind(StrEnum):
    EVIDENCE = "EVIDENCE"
    NODE = "NODE"


class EvidenceSourceChannel(StrEnum):
    MEMORY = "MEMORY"
    AUDIT = "AUDIT"


class PredicateOp(StrEnum):
    EQ = "EQ"
    NE = "NE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    LT = "LT"
    LE = "LE"
    GT = "GT"
    GE = "GE"


@dataclass(frozen=True, slots=True)
class TypeSpec:
    base: PrimitiveType
    container: ContainerKind = ContainerKind.SCALAR

    def canonical(self) -> str:
        if self.container is ContainerKind.SCALAR:
            return self.base.value
        return f"{self.container.value}[{self.base.value}]"


_TYPE_RE = re.compile(r"^(OPTIONAL|LIST|SET)\[([A-Z_]+)\]$")


def parse_type_spec(text: str) -> TypeSpec:
    text = text.strip()
    if text in PrimitiveType._value2member_map_:
        return TypeSpec(PrimitiveType(text))
    match = _TYPE_RE.fullmatch(text)
    if not match:
        raise ValueError(f"unsupported type expression: {text}")
    container, base = match.groups()
    if base not in PrimitiveType._value2member_map_:
        raise ValueError(f"unknown primitive type: {base}")
    return TypeSpec(PrimitiveType(base), ContainerKind(container))


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    dtype: TypeSpec
    required: bool = True
    description: str = ""


@dataclass(frozen=True, slots=True)
class SourceSpec:
    kind: SourceKind
    node_id: str | None = None
    event_types: tuple[str, ...] = ()
    evidence_channel: EvidenceSourceChannel = EvidenceSourceChannel.MEMORY


@dataclass(frozen=True, slots=True)
class PredicateAtom:
    field: str
    op: PredicateOp
    value: Any


@dataclass(frozen=True, slots=True)
class RecordSelector:
    all_of: tuple[PredicateAtom, ...] = ()
    negated: bool = False

    def complement(self) -> "RecordSelector":
        return RecordSelector(self.all_of, not self.negated)


@dataclass(frozen=True, slots=True)
class SemanticObjective:
    text: str


@dataclass(frozen=True, slots=True)
class SourceRequirement:
    source_node_id: str
    required_fields: tuple[tuple[str, TypeSpec | None], ...]


@dataclass(frozen=True, slots=True)
class TransformOpSpec:
    op: OperatorKind
    inputs: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    objective: SemanticObjective | None = None


@dataclass(frozen=True, slots=True)
class TransformPlan:
    ops: tuple[TransformOpSpec, ...]
    output_ref: str = "out"
    source_requirements: tuple[SourceRequirement, ...] = ()

    @property
    def semantic_operator_count(self) -> int:
        return sum(op.op.value.startswith("SEMANTIC_") for op in self.ops)


@dataclass(frozen=True, slots=True)
class MemoryNodeSpec:
    node_id: str
    label: str
    purpose: str
    scope: MemoryScope
    mode: MemoryMode
    schema: tuple[FieldSpec, ...]
    primary_key: tuple[str, ...]
    access: frozenset[AccessMode]
    sources: tuple[SourceSpec, ...]
    transform: TransformPlan
    selector: RecordSelector | None = None

    def field_map(self) -> dict[str, FieldSpec]:
        return {field.name: field for field in self.schema}


@dataclass(frozen=True, slots=True)
class MemoryArchitectureSpec:
    format_version: str
    architecture_id: str
    generation: int
    nodes: tuple[MemoryNodeSpec, ...]

    def node_map(self) -> dict[str, MemoryNodeSpec]:
        return {node.node_id: node for node in self.nodes}

    def get(self, node_id: str) -> MemoryNodeSpec:
        try:
            return self.node_map()[node_id]
        except KeyError as exc:
            raise KeyError(f"unknown memory architecture node: {node_id}") from exc

    def downstream_ids(self, node_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                node.node_id
                for node in self.nodes
                if any(source.kind is SourceKind.NODE and source.node_id == node_id for source in node.sources)
            )
        )

    def topological_order(self) -> tuple[str, ...]:
        nodes = self.node_map()
        indegree = {node_id: 0 for node_id in nodes}
        children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for node in self.nodes:
            for source in node.sources:
                if source.kind is SourceKind.NODE and source.node_id in nodes:
                    indegree[node.node_id] += 1
                    children[source.node_id].append(node.node_id)
        ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for child in sorted(children[node_id]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort()
        if len(order) != len(nodes):
            raise ValueError("memory architecture contains a cycle")
        return tuple(order)
