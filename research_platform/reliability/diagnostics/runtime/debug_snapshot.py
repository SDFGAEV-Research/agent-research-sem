from __future__ import annotations

from dataclasses import asdict, dataclass

from research_platform.reliability.diagnostics.api import DiagnosticEvidencePort, MetricQueryPort

from .causal_contracts import CausalGraphSnapshot
from .causal_graph import CausalGraphService
from .diagnosis import FailureDiagnosisService


@dataclass(frozen=True, slots=True)
class DebugSnapshot:
    object_id: str
    object: dict[str, object]
    diagnosis: dict[str, object] | None
    causal_graph: CausalGraphSnapshot
    timeline: tuple[dict[str, object], ...]
    recent_state_writers: tuple[dict[str, object], ...]
    operations_open_at_time: tuple[dict[str, object], ...]
    nearby_metrics: tuple[dict[str, object], ...]


class DebugSnapshotService:
    """One consistent diagnostic read join; evidence and metric backends are independent ports."""

    def __init__(self, evidence: DiagnosticEvidencePort, metrics: MetricQueryPort | None = None) -> None:
        self.evidence = evidence
        self.diagnosis = FailureDiagnosisService(evidence)
        self.metrics = metrics

    def build(
        self,
        object_id: str,
        *,
        seconds: float = 30.0,
        metric_limit: int = 2000,
    ) -> DebugSnapshot:
        with self.evidence.read_session() as index:
            obj = index.locate(object_id)
            if obj is None:
                raise KeyError(f"object not found: {object_id}")
            context = obj.get("context") or {}
            run_id = str(context.get("run_id")) if isinstance(context, dict) and context.get("run_id") else None
            timestamp = obj.get("created_at", obj.get("timestamp"))
            timeline = (
                index.around(run_id=run_id, timestamp=float(timestamp), seconds=seconds)
                if run_id and timestamp is not None
                else ()
            )
            writers = (
                index.recent_state_writers(run_id=run_id, before=float(timestamp), limit=20)
                if run_id and timestamp is not None
                else ()
            )
            open_operations = (
                index.operations_open_at(run_id=run_id, timestamp=float(timestamp), limit=50)
                if run_id and timestamp is not None
                else ()
            )
            diagnosis = (
                asdict(self.diagnosis.why(object_id, window_seconds=seconds, index=index))
                if obj.get("failure_id")
                else None
            )
            graph = CausalGraphService(self.evidence).build(object_id, index=index)
        nearby_metrics: tuple[dict[str, object], ...] = ()
        if self.metrics is not None and run_id:
            decision_cycle_id = (
                str(context.get("decision_cycle_id"))
                if isinstance(context, dict) and context.get("decision_cycle_id")
                else None
            )
            nearby_metrics = self.metrics.query(
                run_id=run_id,
                decision_cycle_id=decision_cycle_id,
                limit=metric_limit,
            )
        return DebugSnapshot(
            object_id,
            obj,
            diagnosis,
            graph,
            timeline,
            writers,
            open_operations,
            nearby_metrics,
        )
