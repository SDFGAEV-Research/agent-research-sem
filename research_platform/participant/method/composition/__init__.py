"""Explicit Participant/Method composition with reproducible provider evidence."""

from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.architecture.api.capabilities import (
    METHOD_COMPOSITION_PORTS_V1,
)
from research_platform.governance.architecture.api.capability_composition import (
    BindingPlan,
    CapabilityOffer,
    CompositionContract,
    CompositionIdentity,
    CompositionSubject,
    interface_contract_digest,
)
from research_platform.governance.architecture.runtime.capability_composition import (
    CapabilityCompositionPlanner,
)
from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.participant.method.api import (
    MethodCompositionPorts,
    MethodEndpointFactoryPort,
    MethodObservationOutboxFactoryPort,
    MethodSystemBinding,
)
from research_platform.participant.method.runtime import (
    DefaultMethodEndpointFactory,
    DefaultMethodObservationOutboxFactory,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity


_METHOD_SYSTEM = SystemIdentity("participant", ("method",))
_METHOD_SUBJECT = CompositionSubject.system_subject(_METHOD_SYSTEM)


@dataclass(frozen=True, slots=True)
class MethodSystemProviders:
    """Concrete method-system providers chosen only by a composition root."""

    endpoint_factory: MethodEndpointFactoryPort
    observation_outbox_factory: MethodObservationOutboxFactoryPort
    provider_identity: str
    configuration_digest: str


def compose_method_system(
    *,
    providers: MethodSystemProviders,
    planner: CapabilityCompositionPlanner,
    scope: ScopeIdentity = PLATFORM_SCOPE,
    parent_plan_digest: str | None = None,
) -> MethodSystemBinding:
    """Expose participant-method composition ports without a hidden default."""

    offer = CapabilityOffer(
        offer_id="participant.method.composition-ports",
        owner=_METHOD_SUBJECT,
        scope=scope,
        capability=METHOD_COMPOSITION_PORTS_V1,
        interface_digest=interface_contract_digest(MethodCompositionPorts),
        provider_identity=providers.provider_identity,
        configuration_digest=providers.configuration_digest,
    )
    plan = planner.freeze(
        CompositionIdentity(
            "participant.method",
            scope,
            owner=_METHOD_SUBJECT,
            parent_plan_digest=parent_plan_digest,
        ),
        (CompositionContract(_METHOD_SUBJECT, scope, offers=(offer,)),),
    )
    return MethodSystemBinding(
        ports=MethodCompositionPorts(
            endpoint_factory=providers.endpoint_factory,
            observation_outbox_factory=providers.observation_outbox_factory,
        ),
        plan=plan,
        offer=offer,
    )


def compose_default_method_system(
    *,
    planner: CapabilityCompositionPlanner,
    scope: ScopeIdentity = PLATFORM_SCOPE,
    parent_plan_digest: str | None = None,
) -> MethodSystemBinding:
    """Select the platform's default method providers at the system boundary."""

    return compose_method_system(
        providers=MethodSystemProviders(
            endpoint_factory=DefaultMethodEndpointFactory(),
            observation_outbox_factory=DefaultMethodObservationOutboxFactory(),
            provider_identity="participant.method.default-composition.v1",
            configuration_digest=canonical_digest(
                {
                    "endpoint_factory": "participant.method.default-endpoint.v1",
                    "observation_outbox_factory": "participant.method.default-outbox.v1",
                }
            ),
        ),
        planner=planner,
        scope=scope,
        parent_plan_digest=parent_plan_digest,
    )


__all__ = [
    "MethodSystemProviders",
    "compose_default_method_system",
    "compose_method_system",
]
