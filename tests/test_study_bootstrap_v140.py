from __future__ import annotations

from tests_support import environment_effect_intent

from tests._concurrency_support import OwnedForensicStore as ForensicStore
from research_platform.reliability.effect.api import PreparedEffectHandle

from pathlib import Path
import tempfile

from research_platform.platform.composition.operation import build_operation_executor
from research_platform.platform.composition.operation_forensics import OperationForensicFailureSink
from research_platform.reliability.effect.api import EffectIntent
from research_platform.environment.runtime.api import ActionRequest, action_request_digest
from research_platform.platform.kernel import ComponentIdentity, ExecutionContext, OperationRequest
from research_platform.execution.workflow.implementations.context_action import StudyOperationFailureReferenceProjector


def test_bootstrap_accepts_explicit_workflow_causal_projection():
    context = ExecutionContext(
        "run", "trace", "span", study_id="study", task_id="task", decision_cycle_id="dc",
        checkpoint_id="cp", participant_generations=(("environment", "world-1"),),
    )
    action = ActionRequest("action_dc", "move", {"n": 1}, context)
    handle = PreparedEffectHandle.build(
        request_id=action.action_id,
        request_digest=action_request_digest(action),
        provider_schema="provider.tx.v1",
        opaque_payload=b"private-token",
    )
    component = ComponentIdentity("environment.e", "e", "1", "1", "g")
    intent = environment_effect_intent(action, component, operation_id="dc:environment.act", recovery_handle=handle)
    request = OperationRequest(
        "dc:environment.action_intent.prepare",
        "invocation:test-bootstrap",
        "environment.action_intent.prepare",
        context,
        component,
        component,
        intent,
        "v1",
        "payload-digest",
        idempotency_key=intent.intent_id,
    )
    with tempfile.TemporaryDirectory() as td, ForensicStore(Path(td)) as store:
        executor = build_operation_executor(
            failure_sink=OperationForensicFailureSink(
                store, reference_projector=StudyOperationFailureReferenceProjector()
            ),
            event_sink=store,
        )
        result = executor.execute(request, lambda _: (_ for _ in ()).throw(OSError("disk")))
        assert result.failure_id
        failure = store.failures.verified_payloads_after(0)[3][0]
        assert f"action-intent:{intent.intent_id}" in failure["correlation_refs"]
        assert "provider-recovery-schema:provider.tx.v1" in failure["correlation_refs"]
        assert "private-token" not in str(failure)
