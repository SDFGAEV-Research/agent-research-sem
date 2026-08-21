from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.governance.architecture.composition.capabilities import (
    HOST_OPERATING_SYSTEM_ROUTE_V1,
)
from research_platform.governance.architecture.composition.capability_graph import (
    BindingPlan,
    CapabilityCompositionPlanner,
    CapabilityOffer,
    CompositionIdentity,
    SystemCompositionContract,
    interface_contract_digest,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity

from ..api import OperatingSystemRoute
from ..providers import LocalOperatingSystemRoute


_HOST_SYSTEM = SystemIdentity("runtime", ("host",))


@dataclass(frozen=True, slots=True)
class HostComposition:
    """Frozen host binding evidence plus the one injected runtime port."""

    operating_system: OperatingSystemRoute
    plan: BindingPlan
    operating_system_offer: CapabilityOffer


def compose_local_host(
    *,
    planner: CapabilityCompositionPlanner,
    scope: ScopeIdentity = PLATFORM_SCOPE,
    parent_plan_digest: str | None = None,
) -> HostComposition:
    """Select the local host provider at one explicit composition root.

    Runtime modules must receive ``OperatingSystemRoute`` directly; they never
    construct this provider or ask a container to find it.
    """

    operating_system = LocalOperatingSystemRoute()
    offer = CapabilityOffer(
        offer_id="runtime.host.local-operating-system-route",
        owner=_HOST_SYSTEM,
        scope=scope,
        capability=HOST_OPERATING_SYSTEM_ROUTE_V1,
        interface_digest=interface_contract_digest(OperatingSystemRoute),
        provider_identity="runtime.host.local-operating-system-route.v1",
        configuration_digest=canonical_digest(
            {
                "family": operating_system.identity.family,
                "system_name": operating_system.identity.system_name,
                "release": operating_system.identity.release,
                "machine": operating_system.identity.machine,
            }
        ),
    )
    plan = planner.freeze(
        CompositionIdentity(
            "runtime.host",
            scope,
            owner_system=_HOST_SYSTEM,
            parent_plan_digest=parent_plan_digest,
        ),
        (SystemCompositionContract(_HOST_SYSTEM, scope, offers=(offer,)),),
    )
    return HostComposition(operating_system, plan, offer)


__all__ = ["HostComposition", "compose_local_host"]
