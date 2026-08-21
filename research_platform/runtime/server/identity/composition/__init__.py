from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.governance.architecture.api.capabilities import (
    HOST_OPERATING_SYSTEM_ROUTE_V1,
    SERVER_CONNECTION_FACTORY_V1,
)
from research_platform.governance.architecture.api.capability_composition import (
    BindingPlan,
    CapabilityOffer,
    CapabilityRequirement,
    CompositionContract,
    CompositionIdentity,
    CompositionSubject,
    RequirementAddress,
    interface_contract_digest,
)
from research_platform.governance.architecture.runtime.capability_composition import (
    CapabilityCompositionPlanner,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.runtime.host.api import OperatingSystemRoute
from research_platform.runtime.server.identity.api import ServerConnectionFactoryPort
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity

from research_platform.runtime.server.identity.providers import EnvironmentSSHServerConnectionFactory


_SERVER_IDENTITY_SYSTEM = SystemIdentity("runtime", ("server", "identity"))
_SERVER_IDENTITY_SUBJECT = CompositionSubject.system_subject(_SERVER_IDENTITY_SYSTEM)


@dataclass(frozen=True, slots=True)
class ServerIdentityComposition:
    """Explicit server-identity assembly with its immutable binding evidence."""

    connection_factory: ServerConnectionFactoryPort
    plan: BindingPlan
    connection_factory_offer: CapabilityOffer


def compose_environment_server_identity(
    *,
    operating_system: OperatingSystemRoute,
    host_operating_system_offer: CapabilityOffer,
    planner: CapabilityCompositionPlanner,
    scope: ScopeIdentity = PLATFORM_SCOPE,
    parent_plan_digest: str | None = None,
) -> ServerIdentityComposition:
    """Bind environment-backed SSH identity to the host OS route explicitly."""

    host_requirement = CapabilityRequirement(
        RequirementAddress(_SERVER_IDENTITY_SUBJECT, "host-operating-system-route"),
        scope,
        HOST_OPERATING_SYSTEM_ROUTE_V1,
        interface_contract_digest(OperatingSystemRoute),
    )
    factory_offer = CapabilityOffer(
        offer_id="runtime.server.environment-ssh-connection-factory",
        owner=_SERVER_IDENTITY_SUBJECT,
        scope=scope,
        capability=SERVER_CONNECTION_FACTORY_V1,
        interface_digest=interface_contract_digest(ServerConnectionFactoryPort),
        provider_identity="runtime.server.environment-ssh-connection-factory.v1",
        configuration_digest=canonical_digest(
            {"provider": "environment-ssh", "host_offer": host_operating_system_offer.offer_id}
        ),
    )
    plan = planner.freeze(
        CompositionIdentity(
            "runtime.server.identity",
            scope,
            owner=_SERVER_IDENTITY_SUBJECT,
            parent_plan_digest=parent_plan_digest,
        ),
        (
            CompositionContract(
                _SERVER_IDENTITY_SUBJECT,
                scope,
                offers=(factory_offer,),
                requirements=(host_requirement,),
            ),
        ),
        imported_offers=(host_operating_system_offer,),
    )
    factory = EnvironmentSSHServerConnectionFactory(operating_system)
    return ServerIdentityComposition(factory, plan, factory_offer)


__all__ = ["ServerIdentityComposition", "compose_environment_server_identity"]
