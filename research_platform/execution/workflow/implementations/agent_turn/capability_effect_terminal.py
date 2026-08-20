from __future__ import annotations

from research_platform.participant.capability.api import CapabilityResult
from research_platform.reliability.effect.api import (
    EffectCompletionEvidence,
    EffectIntent,
    EffectReconciliationDisposition,
)
from research_platform.platform.kernel import ComponentIdentity, ExecutionContext, OperationResult, canonical_digest
from research_platform.execution.workflow.api import EffectIntentOperationPort


def terminalize_capability_effect(
    intent_operations: EffectIntentOperationPort,
    *,
    intent: EffectIntent,
    result: CapabilityResult,
    disposition: EffectReconciliationDisposition,
    consumer_component: ComponentIdentity,
    completion_operation_id: str,
    context: ExecutionContext,
) -> tuple[OperationResult[object], ...]:
    assert result.effect is not None
    if disposition is EffectReconciliationDisposition.NOT_APPLIED:
        _, operation = intent_operations.record_not_applied(intent, result.effect, context)
        return (operation,)
    evidence = EffectCompletionEvidence(
        completion_key=intent.request_id,
        completion_operation_id=completion_operation_id,
        consumer_component_digest=canonical_digest(consumer_component),
        consumer_generation=context.generation("agent"),
    )
    _, operation = intent_operations.record_consumed(intent, evidence, context)
    return (operation,)


__all__ = ["terminalize_capability_effect"]
