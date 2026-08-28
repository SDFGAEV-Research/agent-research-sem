from __future__ import annotations

"""Read-only structural probes over a pinned architecture and telemetry cut."""

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from ..architecture import MemoryArchitectureSpec
from .slicing import AutomaticSliceDiscovery
from .telemetry import QueryRecordObservation, TelemetryBook

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
