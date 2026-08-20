from pathlib import Path

from research_platform.reliability.forensics.composition import ForensicStore
from research_platform.reliability.forensics.runtime.diagnostic_adapter import ForensicDiagnosticEvidence
from research_platform.platform.kernel import ExecutionContext
from research_platform.reliability.failure.api import RecoveryAction, RiskLevel
from research_platform.reliability.failure.api import build_failure
from research_platform.reliability.forensics.api.mutation import MutationRecord
from research_platform.reliability.diagnostics.runtime import DebugSnapshotService
from research_platform.observability.telemetry.metric.composition import build_default_registry
from research_platform.observability.telemetry.metric.providers import TelemetrySQLiteBackend
from research_platform.observability.telemetry.metric.runtime import TelemetryStore
from research_platform.observability.telemetry.metric.providers import SQLiteTelemetryReader


def _ctx():
    return ExecutionContext(run_id="r1", trace_id="tr1", span_id="sp1", task_id="t1", decision_cycle_id="dc1", operation_id="op1", component_id="agent.planner")


def test_debug_snapshot_joins_failure_graph_writers_and_metrics(tmp_path: Path):
    root=tmp_path/'f'; store=ForensicStore(root)
    ctx=_ctx()
    store.append_mutation(MutationRecord(mutation_id="m1", state_name="agent.plan", aggregate_id="agent:r1", expected_version=0, new_version=1, old_digest="a", new_digest="b", component_id="agent.planner", operation_id="op0", context=ctx))
    failure=build_failure(component_id="agent.planner", operation_id="op1", operation_type="plan", stage="inference", failure_domain="LLM", failure_code="MODEL_ERROR", context=ctx, exc=RuntimeError("boom"), recommended_recovery=RecoveryAction.RETRY_OPERATION, scientific_validity_risk=RiskLevel.LOW)
    store.append_failure(failure)
    db=tmp_path/'telemetry.sqlite'; ts=TelemetryStore(build_default_registry(), TelemetrySQLiteBackend(db)); ts.observe(ctx,"llm.request.latency",1.5,role="planner",model="m",endpoint="local",status="error")
    snap=DebugSnapshotService(ForensicDiagnosticEvidence(ForensicStore(root,read_only=True)), SQLiteTelemetryReader(db)).build(failure.failure_id)
    assert snap.diagnosis and snap.diagnosis["headline"] == "LLM:MODEL_ERROR"
    assert any(x.get("mutation_id") == "m1" for x in snap.recent_state_writers)
    assert any(x["metric"] == "llm.request.latency" for x in snap.nearby_metrics)
    assert any(n["kind"] == "operation" for n in snap.causal_graph["nodes"])


def test_graph_projectors_remain_explicit_reference_only(tmp_path: Path):
    root=tmp_path/'f'; store=ForensicStore(root); ctx=_ctx()
    failure=build_failure(component_id="x", operation_id="op1", operation_type="x", stage="x", failure_domain="X", failure_code="Y", context=ctx, exc=RuntimeError("x"))
    store.append_failure(failure)
    snap=DebugSnapshotService(ForensicDiagnosticEvidence(ForensicStore(root,read_only=True))).build(failure.failure_id)
    assert all(e["relation"] != "temporally_caused_by" for e in snap.causal_graph["edges"])
