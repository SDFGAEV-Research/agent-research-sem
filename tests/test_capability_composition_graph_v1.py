from __future__ import annotations

import pytest

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.governance.system_registry.runtime import build_default_system_registry
from research_platform.governance.architecture.composition.capability_graph import (
    AmbiguousCapabilityProvider,
    CapabilityCompositionPlanner,
    CapabilityDependencyCycle,
    CapabilityInterfaceMismatch,
    CapabilityKey,
    CapabilityOffer,
    CapabilityRequirement,
    CompositionIdentity,
    CompositionTopologyError,
    ProviderSelection,
    RequirementAddress,
    SystemCompositionContract,
    interface_contract_digest,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.runtime.host.api import OperatingSystemRoute
from research_platform.runtime.server.identity.api import ServerConnectionFactoryPort
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind
from research_platform.scope.runtime import InMemoryScopeRegistry


HOST_ROUTE = CapabilityKey("runtime.host", "operating-system-route", 1)
SERVER_FACTORY = CapabilityKey("runtime.server", "connection-factory", 1)


def _scope_registry() -> InMemoryScopeRegistry:
    scopes = InMemoryScopeRegistry()
    workspace = ScopeIdentity(ScopeKind.WORKSPACE, "workspace")
    program = ScopeIdentity(ScopeKind.PROGRAM, "program")
    project = ScopeIdentity(ScopeKind.PROJECT, "project")
    scopes.register(workspace, PLATFORM_SCOPE)
    scopes.register(program, workspace)
    scopes.register(project, program)
    return scopes


def _offer(
    *,
    offer_id: str,
    owner: SystemIdentity,
    capability: CapabilityKey,
    interface: type,
    scope: ScopeIdentity = PLATFORM_SCOPE,
    exported: bool = True,
) -> CapabilityOffer:
    return CapabilityOffer(
        offer_id=offer_id,
        owner=owner,
        scope=scope,
        capability=capability,
        interface_digest=interface_contract_digest(interface),
        provider_identity=f"{offer_id}.provider",
        configuration_digest=canonical_digest({"offer_id": offer_id, "scope": scope.key}),
        exported_to_descendants=exported,
    )


def _requirement(
    *,
    consumer: SystemIdentity,
    requirement_id: str,
    capability: CapabilityKey,
    interface: type,
    scope: ScopeIdentity = PLATFORM_SCOPE,
) -> CapabilityRequirement:
    return CapabilityRequirement(
        address=RequirementAddress(consumer, requirement_id),
        scope=scope,
        capability=capability,
        interface_digest=interface_contract_digest(interface),
    )


def test_plan_is_stable_metadata_and_never_a_runtime_container() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = SystemIdentity("runtime", ("host",))
    server = SystemIdentity("runtime", ("server",))
    offer = _offer(
        offer_id="local.host-route",
        owner=host,
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    requirement = _requirement(
        consumer=server,
        requirement_id="host-route",
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)
    plan = planner.freeze(
        CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, SystemIdentity("runtime")),
        (
            SystemCompositionContract(host, PLATFORM_SCOPE, offers=(offer,)),
            SystemCompositionContract(server, PLATFORM_SCOPE, requirements=(requirement,)),
        ),
    )

    assert plan.bindings_for(requirement.address)[0].offer == offer
    assert len(plan.digest) == 64
    assert not hasattr(plan, "resolve")
    assert not hasattr(plan, "get")


def test_ambiguous_provider_requires_explicit_selection() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = SystemIdentity("runtime", ("host",))
    server = SystemIdentity("runtime", ("server",))
    requirement = _requirement(
        consumer=server,
        requirement_id="host-route",
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    contracts = (
        SystemCompositionContract(
            host,
            PLATFORM_SCOPE,
            offers=(
                _offer(offer_id="host.a", owner=host, capability=HOST_ROUTE, interface=OperatingSystemRoute),
                _offer(offer_id="host.b", owner=host, capability=HOST_ROUTE, interface=OperatingSystemRoute),
            ),
        ),
        SystemCompositionContract(server, PLATFORM_SCOPE, requirements=(requirement,)),
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)
    identity = CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, SystemIdentity("runtime"))

    with pytest.raises(AmbiguousCapabilityProvider):
        planner.freeze(identity, contracts)

    plan = planner.freeze(
        identity,
        contracts,
        selections=(ProviderSelection(requirement.address, ("host.b",)),),
    )
    assert plan.bindings_for(requirement.address)[0].offer.offer_id == "host.b"


def test_incompatible_interface_digest_fails_before_binding() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = SystemIdentity("runtime", ("host",))
    server = SystemIdentity("runtime", ("server",))
    offer = _offer(
        offer_id="local.host-route",
        owner=host,
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    requirement = _requirement(
        consumer=server,
        requirement_id="host-route",
        capability=HOST_ROUTE,
        interface=ServerConnectionFactoryPort,
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)

    with pytest.raises(CapabilityInterfaceMismatch):
        planner.freeze(
            CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, SystemIdentity("runtime")),
            (
                SystemCompositionContract(host, PLATFORM_SCOPE, offers=(offer,)),
                SystemCompositionContract(server, PLATFORM_SCOPE, requirements=(requirement,)),
            ),
        )


def test_plan_rejects_cycles_and_nonlocal_child_composition() -> None:
    systems = build_default_system_registry()
    scopes = _scope_registry()
    host = SystemIdentity("runtime", ("host",))
    server = SystemIdentity("runtime", ("server",))
    host_offer = _offer(
        offer_id="host.route",
        owner=host,
        capability=HOST_ROUTE,
        interface=OperatingSystemRoute,
    )
    server_offer = _offer(
        offer_id="server.factory",
        owner=server,
        capability=SERVER_FACTORY,
        interface=ServerConnectionFactoryPort,
    )
    planner = CapabilityCompositionPlanner(systems=systems, scopes=scopes)
    identity = CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, SystemIdentity("runtime"))
    with pytest.raises(CapabilityDependencyCycle):
        planner.freeze(
            identity,
            (
                SystemCompositionContract(
                    host,
                    PLATFORM_SCOPE,
                    offers=(host_offer,),
                    requirements=(
                        _requirement(
                            consumer=host,
                            requirement_id="server-factory",
                            capability=SERVER_FACTORY,
                            interface=ServerConnectionFactoryPort,
                        ),
                    ),
                ),
                SystemCompositionContract(
                    server,
                    PLATFORM_SCOPE,
                    offers=(server_offer,),
                    requirements=(
                        _requirement(
                            consumer=server,
                            requirement_id="host-route",
                            capability=HOST_ROUTE,
                            interface=OperatingSystemRoute,
                        ),
                    ),
                ),
            ),
        )

    with pytest.raises(CompositionTopologyError):
        planner.freeze(
            CompositionIdentity("runtime.infrastructure", PLATFORM_SCOPE, SystemIdentity("runtime")),
            (
                SystemCompositionContract(
                    SystemIdentity("runtime", ("server", "identity")),
                    PLATFORM_SCOPE,
                ),
            ),
        )
