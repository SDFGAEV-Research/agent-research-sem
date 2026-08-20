from pathlib import Path
import tempfile
import unittest

from research_platform.governance.architecture import ArchitectureAudit, ComponentDescriptor
from research_platform.reliability.failure.api import RecoveryAction, RiskLevel
from research_platform.reliability.forensics.runtime import triage
from research_platform.reliability.failure.api import build_failure
from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity
from research_platform.participant.method.api import MethodIdentity
from research_platform.model.serving.api import ModelPhase, ModelRunState
from research_platform.model.serving.runtime import RecoveryPlanner
from research_platform.model.request.prompt.runtime import PromptRegistry, default_prompt_specs
from research_platform.observability.telemetry.metric.composition import build_default_registry
from research_platform.observability.telemetry.metric.runtime import InMemoryMetricRecorder


class PlatformCoreTests(unittest.TestCase):
    def test_failure_is_precisely_locatable(self):
        ctx = ExecutionContext(run_id="r1", trace_id="t1", span_id="s1", task_id="task7", decision_cycle_id="dc9", operation_id="op3")
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            f = build_failure(component_id="method.evolution", failure_domain="METHOD_EVOLUTION", failure_code="SYNTHESIS_FAILED", stage="synthesis", context=ctx, exc=exc, operation_id="op3", recommended_recovery=RecoveryAction.MANUAL_DIAGNOSIS, scientific_validity_risk=RiskLevel.HIGH)
        r = triage(f)
        self.assertIn("task7", r.exact_location)
        self.assertIn("dc9", r.exact_location)
        self.assertEqual(r.scientific_risk, "high")

    def test_metrics_reject_unknown_dimensions(self):
        registry = build_default_registry()
        rec = InMemoryMetricRecorder(registry)
        rec.observe("model.ttft", 0.2, model="m", engine="e", replica="0")
        with self.assertRaises(ValueError):
            rec.observe("model.ttft", 0.2, model="m", engine="e", replica="0", surprise="x")

    def test_prompt_generation_is_atomic(self):
        reg = PromptRegistry()
        specs = default_prompt_specs()
        reg.publish("g1", specs)
        self.assertEqual(reg.generation, "g1")
        self.assertTrue(reg.get("planner.v6").digest)
        self.assertIn("Verified current state", reg.get("planner.v6").text)

    def test_recovery_refuses_quality_or_identity_drift(self):
        base = ImmutableModelIdentity("m", "Qwen/Qwen3.6-35B-A3B", "abc", "sglang", "0.5.13", "bfloat16", None, 262144)
        changed = ImmutableModelIdentity("m", "Qwen/Qwen3.6-35B-A3B", "abc", "sglang", "0.5.13", "float16", None, 262144)
        state = ModelRunState.initial("run", base, "d"*64).transition(ModelPhase.INVENTORY).transition(ModelPhase.PREPARE).transition(ModelPhase.INTERRUPTED)
        with self.assertRaises(ValueError):
            RecoveryPlanner().plan(state,changed,state.deployment_digest)

    def test_recovery_refuses_deployment_stack_drift_even_when_logical_model_identity_matches(self):
        base = ImmutableModelIdentity("m", "Qwen/Qwen3.6-35B-A3B", "abc", "sglang", "0.5.13", "bfloat16", None, 262144)
        state = ModelRunState.initial("run", base, "a"*64).transition(ModelPhase.INVENTORY).transition(ModelPhase.PREPARE).transition(ModelPhase.INTERRUPTED)
        with self.assertRaises(ValueError):
            RecoveryPlanner().plan(state, base, "b"*64)

    def test_recovery_is_exact_and_complete(self):
        base = ImmutableModelIdentity("m", "Qwen/Qwen3.6-35B-A3B", "abc", "sglang", "0.5.13", "bfloat16", None, 262144)
        state = ModelRunState.initial("run", base, "d"*64).transition(ModelPhase.INVENTORY).transition(ModelPhase.PREPARE).transition(ModelPhase.INTERRUPTED)
        plan = RecoveryPlanner().plan(state,base,state.deployment_digest)
        self.assertEqual(plan.frozen_identity, base)
        self.assertEqual(plan.steps[-1].value, "resume_run_exact")

    def test_architecture_firewall_catches_audit_to_method(self):
        d = (ComponentDescriptor("bad", data_domains_read=("j_audit",), data_domains_write=("method_memory",)),)
        v = ArchitectureAudit(d, state_owners={}, side_effect_owners={}, forbidden_dataflows={("j_audit", "method_memory")}).run()
        self.assertEqual(v[0].kind, "forbidden_dataflow")

    def test_method_api_contains_no_minecraft_semantics(self):
        fields = MethodIdentity.__dataclass_fields__
        self.assertNotIn("minecraft", " ".join(fields).lower())


if __name__ == "__main__":
    unittest.main()
