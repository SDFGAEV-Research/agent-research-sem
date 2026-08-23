from __future__ import annotations

"""Read-only Deluxe evolution diagnostics.

The diagnostic plane observes the current method contracts but does not own
memory evidence, candidate acceptance, architecture adoption, or experiment
evaluation.  It is intentionally kept independent of serving implementations
so the same facts can be supplied by Core, Standard, or Deluxe treatments.
"""

from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import StrEnum
import hashlib
import json
import math
import re
from typing import Any, Mapping, Protocol, Sequence

from ..architecture import MemoryArchitectureSpec


class IncidentKind(StrEnum):
    STALE_USE = "STALE_USE"
    RETRIEVAL_MISS = "RETRIEVAL_MISS"
    CONFLICTING_RETRIEVAL = "CONFLICTING_RETRIEVAL"
    EXCESSIVE_RETRIEVAL_COST = "EXCESSIVE_RETRIEVAL_COST"
    UNRESOLVED_MEMORY_INTENT = "UNRESOLVED_MEMORY_INTENT"


@dataclass(frozen=True, slots=True)
class MemoryIncident:
    incident_id: str
    kind: IncidentKind
    task_id: str
    intent: str
    node_ids: tuple[str, ...]
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.incident_id.strip() or not self.task_id.strip() or not self.intent.strip():
            raise ValueError("diagnostic incident identity is required")
        if any(not node_id.strip() for node_id in self.node_ids):
            raise ValueError("diagnostic incident node ids must be non-empty")
        if not isinstance(self.detail, Mapping):
            raise TypeError("diagnostic incident detail must be a mapping")


@dataclass(frozen=True, slots=True)
class QueryRecordObservation:
    """The serving result facts needed by diagnostics.

    This is an adapter value, not a second memory record.  A serving provider
    may construct it from its own result type without importing this module's
    telemetry storage.
    """

    node_id: str
    record_id: str
    score: float = 0.0
    payload: Mapping[str, object] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.record_id.strip():
            raise ValueError("diagnostic query record identity is required")
        if not math.isfinite(float(self.score)):
            raise ValueError("diagnostic query record score must be finite")
        if not isinstance(self.payload, Mapping):
            raise TypeError("diagnostic query record payload must be a mapping")
        if any(not ref.strip() for ref in self.source_refs):
            raise ValueError("diagnostic query source refs must be non-empty")
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("diagnostic query source refs must be unique")


@dataclass(frozen=True, slots=True)
class QueryObservation:
    query_id: str
    task_id: str
    intent: str
    opportunity_key: str | None
    selected_nodes: tuple[str, ...]
    returned_node_ids: tuple[str, ...]
    returned_record_ids: tuple[str, ...]
    top_score: float
    record_count: int
    source_ref_count: int

    def __post_init__(self) -> None:
        if not self.query_id.strip() or not self.task_id.strip() or not self.intent.strip():
            raise ValueError("diagnostic query identity is required")
        if any(not node_id.strip() for node_id in (*self.selected_nodes, *self.returned_node_ids)):
            raise ValueError("diagnostic query node ids must be non-empty")
        if any(not record_id.strip() for record_id in self.returned_record_ids):
            raise ValueError("diagnostic query record ids must be non-empty")
        if len(self.returned_node_ids) != len(self.returned_record_ids):
            raise ValueError("diagnostic query returned node/record cardinality mismatch")
        if len(self.selected_nodes) != len(set(self.selected_nodes)):
            raise ValueError("diagnostic query selected nodes must be unique")
        if len(self.returned_record_ids) != len(set(self.returned_record_ids)):
            raise ValueError("diagnostic query returned records must be unique")
        if self.record_count != len(self.returned_record_ids):
            raise ValueError("diagnostic query record_count does not match returned records")
        if self.record_count < 0 or self.source_ref_count < 0:
            raise ValueError("diagnostic query counts cannot be negative")
        if not math.isfinite(float(self.top_score)):
            raise ValueError("diagnostic query top_score must be finite")


@dataclass(frozen=True, slots=True)
class TaskObservation:
    task_id: str
    family: str
    success: bool
    utility: float
    blocked_by_prior_progress: bool = False

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.family.strip():
            raise ValueError("diagnostic task identity is required")
        if not isinstance(self.success, bool) or not isinstance(self.blocked_by_prior_progress, bool):
            raise TypeError("diagnostic task boolean facts are invalid")
        if not math.isfinite(float(self.utility)):
            raise ValueError("diagnostic task utility must be finite")


@dataclass(slots=True)
class NodeRuntimeStats:
    selected_count: int = 0
    result_count: int = 0
    query_count: int = 0
    empty_result_count: int = 0
    update_count: int = 0
    records_added: int = 0
    records_removed: int = 0
    full_recompute_count: int = 0
    group_recompute_count: int = 0
    score_sum: float = 0.0

    def __post_init__(self) -> None:
        count_fields = (
            "selected_count",
            "result_count",
            "query_count",
            "empty_result_count",
            "update_count",
            "records_added",
            "records_removed",
            "full_recompute_count",
            "group_recompute_count",
        )
        if any(
            isinstance(getattr(self, name), bool)
            or not isinstance(getattr(self, name), int)
            or getattr(self, name) < 0
            for name in count_fields
        ):
            raise ValueError("diagnostic node counts must be non-negative integers")
        if not math.isfinite(float(self.score_sum)):
            raise ValueError("diagnostic node score_sum must be finite")

    def as_dict(self) -> dict[str, Any]:
        average = self.score_sum / self.result_count if self.result_count else 0.0
        return {**asdict(self), "avg_result_score": average}


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot:
    """Immutable diagnostic cut used by probes, diagnosis, and exact resume."""

    node_stats: Mapping[str, Mapping[str, Any]]
    queries: tuple[QueryObservation, ...]
    incidents: tuple[MemoryIncident, ...]
    tasks: tuple[TaskObservation, ...]
    block_incident_cursor: int = 0
    block_query_cursor: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.node_stats, Mapping):
            raise TypeError("diagnostic node snapshot must be a mapping")
        if any(not str(node_id).strip() or not isinstance(row, Mapping) for node_id, row in self.node_stats.items()):
            raise ValueError("diagnostic node snapshot is malformed")
        query_ids = tuple(row.query_id for row in self.queries)
        incident_ids = tuple(row.incident_id for row in self.incidents)
        task_ids = tuple(row.task_id for row in self.tasks)
        if len(set(query_ids)) != len(query_ids):
            raise ValueError("diagnostic snapshot contains duplicate query ids")
        if len(set(incident_ids)) != len(incident_ids):
            raise ValueError("diagnostic snapshot contains duplicate incident ids")
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("diagnostic snapshot contains duplicate task ids")
        if self.block_incident_cursor < 0 or self.block_incident_cursor > len(self.incidents):
            raise ValueError("diagnostic incident cursor is outside the snapshot")
        if self.block_query_cursor < 0 or self.block_query_cursor > len(self.queries):
            raise ValueError("diagnostic query cursor is outside the snapshot")


class DiagnosticTelemetryPort(Protocol):
    """Write/read seam; storage and platform sinks remain injected."""

    def record_query(
        self,
        *,
        task_id: str,
        intent: str,
        opportunity_key: str | None,
        selected_nodes: Sequence[str],
        records: Sequence[QueryRecordObservation],
        max_reasonable_nodes: int = 3,
        min_useful_score: float = 0.05,
    ) -> QueryObservation: ...

    def record_task(self, observation: TaskObservation) -> None: ...

    def snapshot(self) -> TelemetrySnapshot: ...

    def restore(self, snapshot: TelemetrySnapshot) -> None: ...


@dataclass(slots=True)
class TelemetryBook:
    """Bounded-domain diagnostic book with explicit immutable read cuts.

    This object is not the platform telemetry sink.  It is a project-local
    diagnostic projection that can be rebuilt from the platform observations.
    No method-memory write or architecture mutation is exposed here.
    """

    node_stats: dict[str, NodeRuntimeStats] = field(default_factory=dict)
    queries: list[QueryObservation] = field(default_factory=list)
    incidents: list[MemoryIncident] = field(default_factory=list)
    tasks: list[TaskObservation] = field(default_factory=list)
    _block_incident_cursor: int = 0
    _block_query_cursor: int = 0

    def _node(self, node_id: str) -> NodeRuntimeStats:
        if not node_id.strip():
            raise ValueError("diagnostic node id must be non-empty")
        return self.node_stats.setdefault(node_id, NodeRuntimeStats())

    def record_query(
        self,
        *,
        task_id: str,
        intent: str,
        opportunity_key: str | None,
        selected_nodes: Sequence[str],
        records: Sequence[QueryRecordObservation],
        max_reasonable_nodes: int = 3,
        min_useful_score: float = 0.05,
    ) -> QueryObservation:
        if not task_id.strip() or not intent.strip():
            raise ValueError("diagnostic query task_id and intent are required")
        if opportunity_key is not None and not opportunity_key.strip():
            raise ValueError("diagnostic query opportunity_key cannot be empty")
        if max_reasonable_nodes < 0 or not math.isfinite(float(min_useful_score)):
            raise ValueError("diagnostic query thresholds are invalid")
        selected = tuple(str(node_id) for node_id in selected_nodes)
        if any(not node_id.strip() for node_id in selected):
            raise ValueError("diagnostic selected node id must be non-empty")
        if len(selected) != len(set(selected)):
            raise ValueError("diagnostic selected node ids must be unique")
        normalized_records = tuple(records)
        record_ids = tuple(record.record_id for record in normalized_records)
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("diagnostic query records must have unique identities")
        query_id = "qry_" + hashlib.sha256(
            json.dumps(
                [task_id, intent, len(self.queries)],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:16]
        returned_nodes = tuple(record.node_id for record in normalized_records)
        record_ids = tuple(record.record_id for record in normalized_records)
        scores = tuple(float(record.score) for record in normalized_records)
        observation = QueryObservation(
            query_id=query_id,
            task_id=task_id,
            intent=intent,
            opportunity_key=opportunity_key,
            selected_nodes=selected,
            returned_node_ids=returned_nodes,
            returned_record_ids=record_ids,
            top_score=max(scores, default=0.0),
            record_count=len(normalized_records),
            source_ref_count=sum(len(record.source_refs) for record in normalized_records),
        )
        self.queries.append(observation)

        for node_id in selected:
            stats = self._node(node_id)
            stats.query_count += 1
            stats.selected_count += 1
        if not normalized_records:
            for node_id in selected:
                self._node(node_id).empty_result_count += 1
        for record in normalized_records:
            stats = self._node(record.node_id)
            stats.result_count += 1
            stats.score_sum += record.score

        if opportunity_key and not normalized_records:
            self._incident(
                IncidentKind.RETRIEVAL_MISS,
                task_id,
                intent,
                selected,
                {"query_id": query_id},
            )
            self._incident(
                IncidentKind.UNRESOLVED_MEMORY_INTENT,
                task_id,
                intent,
                selected,
                {"query_id": query_id, "reason": "no_result"},
            )
        elif opportunity_key and scores and max(scores) < min_useful_score:
            self._incident(
                IncidentKind.UNRESOLVED_MEMORY_INTENT,
                task_id,
                intent,
                selected,
                {"query_id": query_id, "reason": "low_score", "top_score": max(scores)},
            )
        if len(selected) > max_reasonable_nodes:
            self._incident(
                IncidentKind.EXCESSIVE_RETRIEVAL_COST,
                task_id,
                intent,
                selected,
                {"query_id": query_id, "selected_nodes": len(selected)},
            )

        scalar_values: dict[str, set[str]] = {}
        for record in normalized_records:
            for key, value in record.payload.items():
                if isinstance(value, (str, int, float, bool)):
                    scalar_values.setdefault(str(key), set()).add(repr(value))
        conflicts = {key: sorted(values) for key, values in scalar_values.items() if len(values) >= 3}
        if conflicts:
            self._incident(
                IncidentKind.CONFLICTING_RETRIEVAL,
                task_id,
                intent,
                tuple(sorted(set(returned_nodes))),
                {"query_id": query_id, "fields": conflicts},
            )
        return observation

    def record_node_update(
        self,
        node_id: str,
        *,
        records_added: int = 0,
        records_removed: int = 0,
        full_recompute: bool = False,
        group_recompute: bool = False,
    ) -> None:
        values = (records_added, records_removed)
        if any(not isinstance(value, int) or value < 0 for value in values):
            raise ValueError("diagnostic node update counts must be non-negative integers")
        stats = self._node(node_id)
        stats.update_count += 1
        stats.records_added += records_added
        stats.records_removed += records_removed
        stats.full_recompute_count += int(full_recompute)
        stats.group_recompute_count += int(group_recompute)

    def record_task(self, observation: TaskObservation) -> None:
        """Record a task exactly once; retries must replay the same scientific fact."""

        for current in reversed(self.tasks):
            if current.task_id != observation.task_id:
                continue
            if current != observation:
                raise ValueError(
                    f"diagnostic task outcome drift for completed task: {observation.task_id}"
                )
            return
        self.tasks.append(observation)

    def _incident(
        self,
        kind: IncidentKind,
        task_id: str,
        intent: str,
        node_ids: tuple[str, ...],
        detail: Mapping[str, Any],
    ) -> None:
        raw = json.dumps(
            [kind.value, task_id, intent, len(self.incidents)],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        incident_id = "inc_" + hashlib.sha256(raw).hexdigest()[:16]
        self.incidents.append(
            MemoryIncident(incident_id, kind, task_id, intent, tuple(node_ids), dict(detail))
        )

    def block_delta(self) -> tuple[tuple[MemoryIncident, ...], tuple[QueryObservation, ...]]:
        incidents = tuple(self.incidents[self._block_incident_cursor :])
        queries = tuple(self.queries[self._block_query_cursor :])
        self._block_incident_cursor = len(self.incidents)
        self._block_query_cursor = len(self.queries)
        return incidents, queries

    def snapshot(self) -> TelemetrySnapshot:
        return TelemetrySnapshot(
            node_stats={node_id: stats.as_dict() for node_id, stats in sorted(self.node_stats.items())},
            queries=tuple(self.queries),
            incidents=tuple(self.incidents),
            tasks=tuple(self.tasks),
            block_incident_cursor=self._block_incident_cursor,
            block_query_cursor=self._block_query_cursor,
        )

    def restore(self, snapshot: TelemetrySnapshot) -> None:
        """Restore an immutable diagnostic cut without replaying synthetic observations."""

        restored_stats: dict[str, NodeRuntimeStats] = {}
        fields = tuple(NodeRuntimeStats.__dataclass_fields__)
        for node_id, row in snapshot.node_stats.items():
            if not str(node_id).strip() or not isinstance(row, Mapping):
                raise ValueError("diagnostic node snapshot is malformed")
            missing = tuple(name for name in fields if name not in row)
            unknown = tuple(name for name in row if name not in {*fields, "avg_result_score"})
            if missing or unknown:
                raise ValueError(
                    "diagnostic node snapshot schema mismatch: "
                    f"missing={missing!r} unknown={unknown!r}"
                )
            values = {name: row[name] for name in fields}
            stats = NodeRuntimeStats(**values)
            average = stats.score_sum / stats.result_count if stats.result_count else 0.0
            if "avg_result_score" in row and not math.isclose(
                float(row["avg_result_score"]), average, rel_tol=0.0, abs_tol=1e-12
            ):
                raise ValueError("diagnostic node average score does not match authoritative counts")
            restored_stats[str(node_id)] = stats
        self.node_stats = restored_stats
        self.queries = list(snapshot.queries)
        self.incidents = list(snapshot.incidents)
        self.tasks = list(snapshot.tasks)
        self._block_incident_cursor = snapshot.block_incident_cursor
        self._block_query_cursor = snapshot.block_query_cursor


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def _tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text)}


@dataclass(frozen=True, slots=True)
class NeutralSlice:
    slice_id: str
    support: int
    incident_ids: tuple[str, ...]
    examples: tuple[str, ...]
    shared_tokens: tuple[str, ...]


class AutomaticSliceDiscovery:
    """Ontology-free incident slices; no node/edit recommendation is emitted."""

    def discover(
        self,
        incidents: Sequence[MemoryIncident],
        *,
        max_slices: int = 8,
        threshold: float = 0.30,
    ) -> tuple[NeutralSlice, ...]:
        if max_slices <= 0 or not 0.0 <= threshold <= 1.0:
            raise ValueError("neutral slice limits are invalid")
        clusters: list[dict[str, Any]] = []
        for incident in incidents:
            tokens = _tokens(incident.intent)
            best_index: int | None = None
            best_score = 0.0
            for index, cluster in enumerate(clusters):
                union = cluster["union"]
                score = len(tokens & union) / max(1, len(tokens | union))
                if score > best_score:
                    best_score, best_index = score, index
            if best_index is None or best_score < threshold:
                if len(clusters) >= max_slices:
                    continue
                clusters.append({"union": set(tokens), "intersection": set(tokens), "items": [incident]})
            else:
                cluster = clusters[best_index]
                cluster["union"].update(tokens)
                cluster["intersection"].intersection_update(tokens)
                cluster["items"].append(incident)
        slices: list[NeutralSlice] = []
        for cluster in clusters:
            items = cluster["items"]
            material = "|".join(incident.incident_id for incident in items).encode("utf-8")
            slices.append(
                NeutralSlice(
                    slice_id="slice_" + hashlib.sha256(material).hexdigest()[:12],
                    support=len(items),
                    incident_ids=tuple(incident.incident_id for incident in items[:12]),
                    examples=tuple(incident.intent for incident in items[:4]),
                    shared_tokens=tuple(sorted(cluster["intersection"])[:12]),
                )
            )
        return tuple(sorted(slices, key=lambda item: (-item.support, item.slice_id)))


@dataclass(frozen=True, slots=True)
class ProbeSpec:
    kind: str
    args: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.kind.strip() or not isinstance(self.args, Mapping):
            raise ValueError("structural probe kind and args are required")


@dataclass(frozen=True, slots=True)
class ProbeResult:
    probe_id: str
    kind: str
    facts: Mapping[str, Any]


class StructuralProbeEngine:
    """Fixed, bounded, neutral facts over a pinned architecture/read cut."""

    ALLOWED = frozenset(
        {
            "PROFILE",
            "GET_INCIDENT_EXAMPLES",
            "GET_PAIR_STATS",
            "GET_INTENT_CLUSTER",
            "REQUEST_STRUCTURAL_PROBE",
        }
    )

    def __init__(
        self,
        architecture: MemoryArchitectureSpec,
        store: Mapping[str, Sequence[QueryRecordObservation]],
        telemetry: TelemetryBook,
    ) -> None:
        self.architecture = architecture
        self.store = store
        self.telemetry = telemetry
        self.slicer = AutomaticSliceDiscovery()

    def execute(self, spec: ProbeSpec) -> ProbeResult:
        if spec.kind not in self.ALLOWED:
            raise ValueError(f"structural probe kind is not allowed: {spec.kind}")
        facts = self._facts(spec)
        raw = json.dumps(
            [spec.kind, dict(spec.args), facts],
            sort_keys=True,
            default=repr,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return ProbeResult(
            probe_id="probe_" + hashlib.sha256(raw).hexdigest()[:12],
            kind=spec.kind,
            facts=facts,
        )

    def _facts(self, spec: ProbeSpec) -> Mapping[str, Any]:
        args = dict(spec.args)
        if spec.kind == "PROFILE":
            node_id = str(args.get("node_id", ""))
            node = self.architecture.node_map().get(node_id)
            if node is None:
                return {"error": "unknown_node"}
            stats = self.telemetry.node_stats.get(node_id)
            return {
                "node_id": node_id,
                "record_count": len(self.store.get(node_id, ())),
                "schema_fields": [field.name for field in node.schema],
                "access": sorted(access.value for access in node.access),
                "runtime_stats": stats.as_dict() if stats else {},
            }
        if spec.kind == "GET_INCIDENT_EXAMPLES":
            node_id = str(args.get("node_id", ""))
            kind = str(args.get("kind", ""))
            items = [
                incident
                for incident in self.telemetry.incidents
                if (not node_id or node_id in incident.node_ids)
                and (not kind or incident.kind.value == kind)
            ]
            return {
                "examples": [
                    {
                        "incident_id": incident.incident_id,
                        "kind": incident.kind.value,
                        "intent": incident.intent,
                        "node_ids": list(incident.node_ids),
                    }
                    for incident in items[-8:]
                ]
            }
        if spec.kind == "GET_PAIR_STATS":
            node_a = str(args.get("node_a", ""))
            node_b = str(args.get("node_b", ""))
            both = sum(node_a in query.selected_nodes and node_b in query.selected_nodes for query in self.telemetry.queries)
            selected_a = sum(node_a in query.selected_nodes for query in self.telemetry.queries)
            selected_b = sum(node_b in query.selected_nodes for query in self.telemetry.queries)
            return {
                "node_a": node_a,
                "node_b": node_b,
                "co_selected": both,
                "selected_a": selected_a,
                "selected_b": selected_b,
                "jaccard": both / max(1, selected_a + selected_b - both),
            }
        if spec.kind == "GET_INTENT_CLUSTER":
            target = str(args.get("cluster_id", ""))
            for neutral_slice in self.slicer.discover(self.telemetry.incidents):
                if neutral_slice.slice_id == target:
                    return asdict(neutral_slice)
            return {"error": "unknown_cluster"}

        node_ids = tuple(str(value) for value in args.get("node_ids", ()))[:4]
        facts: dict[str, Any] = {}
        for node_id in node_ids:
            rows = tuple(self.store.get(node_id, ()))
            sampled = rows[:200]
            field_values: dict[str, set[str]] = {}
            source_refs: set[str] = set()
            for row in sampled:
                source_refs.update(row.source_refs)
                for key, value in row.payload.items():
                    if isinstance(value, (str, int, float, bool)):
                        field_values.setdefault(str(key), set()).add(repr(value))
            facts[node_id] = {
                "record_count": len(rows),
                "sampled_record_count": len(sampled),
                "field_distinct_counts": {key: len(values) for key, values in field_values.items()},
                "source_ref_count": len(source_refs),
            }
        return {"nodes": facts}


@dataclass(frozen=True, slots=True)
class StructuralHypothesis:
    hypothesis_id: str
    observation_report_id: str
    text: str
    evidence_refs: tuple[str, ...]
    status: str = "PROPOSED"


@dataclass(slots=True)
class HypothesisRegistry:
    """In-memory diagnostic record; it has no candidate/adoption capability."""

    records: list[StructuralHypothesis] = field(default_factory=list)

    def add(
        self,
        *,
        observation_report_id: str,
        text: str,
        evidence_refs: Sequence[str],
        status: str = "PROPOSED",
    ) -> StructuralHypothesis:
        if not observation_report_id.strip() or not text.strip() or not status.strip():
            raise ValueError("structural hypothesis identity and text are required")
        refs = tuple(sorted(set(str(ref) for ref in evidence_refs if str(ref).strip())))
        raw = f"{observation_report_id}|{text}|{'|'.join(refs)}|{len(self.records)}".encode("utf-8")
        hypothesis = StructuralHypothesis(
            hypothesis_id="hyp_" + hashlib.sha256(raw).hexdigest()[:12],
            observation_report_id=observation_report_id,
            text=text,
            evidence_refs=refs,
            status=status,
        )
        self.records.append(hypothesis)
        return hypothesis

    def recent(self, limit: int = 12) -> tuple[StructuralHypothesis, ...]:
        if limit < 0:
            raise ValueError("hypothesis limit must be non-negative")
        return tuple(self.records[-limit:]) if limit else ()


@dataclass(frozen=True, slots=True)
class AdoptionObservation:
    architecture_generation: int
    accepted: bool


@dataclass(frozen=True, slots=True)
class AdaptiveSlowClockConfig:
    base_horizon_episodes: int = 8
    min_horizon_episodes: int = 4
    max_horizon_episodes: int = 18
    high_symptom_density: float = 0.35
    low_symptom_density: float = 0.08
    recent_edit_penalty: int = 4

    def __post_init__(self) -> None:
        if not 0 < self.min_horizon_episodes <= self.base_horizon_episodes <= self.max_horizon_episodes:
            raise ValueError("slow-clock horizon ordering is invalid")
        if not 0.0 <= self.low_symptom_density <= self.high_symptom_density:
            raise ValueError("slow-clock symptom thresholds are invalid")
        if self.recent_edit_penalty < 0:
            raise ValueError("slow-clock edit penalty must be non-negative")


@dataclass(frozen=True, slots=True)
class NodeHorizon:
    node_id: str
    symptom_density: float
    required_episodes: int


class AdaptiveSlowClock:
    """Observation pacing derived from neutral symptoms, never an edit gate."""

    def __init__(self, config: AdaptiveSlowClockConfig | None = None) -> None:
        self.config = config or AdaptiveSlowClockConfig()

    def horizons(
        self,
        *,
        architecture: MemoryArchitectureSpec,
        telemetry: TelemetryBook,
        recent_adoptions: Sequence[AdoptionObservation],
    ) -> tuple[NodeHorizon, ...]:
        config = self.config
        query_counts = Counter(node_id for query in telemetry.queries[-64:] for node_id in query.selected_nodes)
        incident_counts = Counter(node_id for incident in telemetry.incidents[-64:] for node_id in incident.node_ids)
        recent_accept = next((item for item in reversed(recent_adoptions) if item.accepted), None)
        output: list[NodeHorizon] = []
        for node in architecture.nodes:
            queries = query_counts[node.node_id]
            density = incident_counts[node.node_id] / max(1, queries)
            horizon = config.base_horizon_episodes
            if density >= config.high_symptom_density:
                horizon -= 2
            elif density <= config.low_symptom_density:
                horizon += 2
            if recent_accept is not None and architecture.generation - recent_accept.architecture_generation <= 1:
                horizon += config.recent_edit_penalty
            horizon = max(config.min_horizon_episodes, min(config.max_horizon_episodes, horizon))
            output.append(NodeHorizon(node.node_id, density, horizon))
        return tuple(sorted(output, key=lambda item: item.node_id))

    def allow_review(
        self,
        *,
        architecture: MemoryArchitectureSpec,
        telemetry: TelemetryBook,
        recent_adoptions: Sequence[AdoptionObservation],
        episodes_since_activation: int,
    ) -> tuple[bool, Mapping[str, object]]:
        if episodes_since_activation < 0:
            raise ValueError("slow-clock episode count cannot be negative")
        horizons = self.horizons(
            architecture=architecture,
            telemetry=telemetry,
            recent_adoptions=recent_adoptions,
        )
        symptomatic = tuple(item for item in horizons if item.symptom_density > 0)
        required = min(
            (item.required_episodes for item in symptomatic),
            default=self.config.base_horizon_episodes,
        )
        facts = {
            "required_episodes": required,
            "episodes_since_activation": episodes_since_activation,
            "node_horizons": [asdict(item) for item in horizons],
        }
        return episodes_since_activation >= required, facts


__all__ = [
    "AdaptiveSlowClock",
    "AdaptiveSlowClockConfig",
    "AdoptionObservation",
    "AutomaticSliceDiscovery",
    "DiagnosticTelemetryPort",
    "HypothesisRegistry",
    "IncidentKind",
    "MemoryIncident",
    "NeutralSlice",
    "NodeHorizon",
    "NodeRuntimeStats",
    "ProbeResult",
    "ProbeSpec",
    "QueryObservation",
    "QueryRecordObservation",
    "StructuralHypothesis",
    "StructuralProbeEngine",
    "TaskObservation",
    "TelemetryBook",
    "TelemetrySnapshot",
]
