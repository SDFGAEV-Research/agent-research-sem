from __future__ import annotations

from research_platform.participant.capability.api import (
    CapabilityRequest,
    capability_effect_request_id,
    capability_request_digest,
)
from research_platform.reliability.effect.api import EffectIntent, PreparedEffectHandle
from research_platform.platform.kernel import ComponentIdentity


def build_capability_effect_intent(
    request: CapabilityRequest,
    target: ComponentIdentity,
    operation_id: str,
    handle: PreparedEffectHandle | None = None,
) -> EffectIntent:
    return EffectIntent.build(
        request_id=capability_effect_request_id(request),
        request_digest=capability_request_digest(request),
        operation_id=operation_id,
        provider_component=target,
        context=request.context,
        recovery_handle=handle,
        intent_namespace="capability-effect-intent",
    )


__all__ = ["build_capability_effect_intent"]
