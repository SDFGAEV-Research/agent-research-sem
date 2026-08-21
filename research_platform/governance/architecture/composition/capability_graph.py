"""Typed, frozen composition plans without a runtime service locator.

This module owns only composition metadata and validation.  It deliberately
does not retain provider instances and offers no resolve/get operation.  A
composition root materializes a plan through explicit, typed constructors and
injects the resulting ports into runtime modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import inspect
import re

from research_platform.governance.system_registry.api import (
    SystemIdentity,
    SystemRegistryPort,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.scope.api import ScopeIdentity, ScopeRegistryPort


_TOKEN = re.compile(r"[a-z][a-z0-9_.-]*")
_DIGEST = re.compile(r"[0-9a-f]{64}")


class CompositionContractError(ValueError):
    """A capability contract cannot be safely represented in a binding plan."""


class CompositionTopologyError(CompositionContractError):
    """A composition root attempts to compose a non-local system."""


class CapabilityBindingError(CompositionContractError):
    """A requirement cannot be bound to an eligible provider."""


class MissingCapabilityProvider(CapabilityBindingError):
    pass


class AmbiguousCapabilityProvider(CapabilityBindingError):
    pass


class CapabilityInterfaceMismatch(CapabilityBindingError):
    pass


class CapabilityDependencyCycle(CapabilityBindingError):
    pass


class RequirementCardinality(StrEnum):
    EXACTLY_ONE = "exactly_one"
    ONE_OR_MORE = "one_or_more"


@dataclass(frozen=True, slots=True, order=True)
class CapabilityKey:
    """Stable public identity of one composition-time capability."""

    namespace: str
    name: str
    major_version: int

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.namespace):
            raise CompositionContractError("capability namespace must be a lowercase dotted token")
        if not _TOKEN.fullmatch(self.name):
            raise CompositionContractError("capability name must be a lowercase dotted token")
        if self.major_version <= 0:
            raise CompositionContractError("capability major_version must be positive")

    @property
    def value(self) -> str:
        return f"{self.namespace}.{self.name}.v{self.major_version}"


def interface_contract_digest(interface: type) -> str:
    """Fingerprint the public callable/property surface of a port interface.

    The fingerprint is source-independent and is only used while composing a
    plan.  It prevents two providers with the same textual capability key but
    incompatible port surfaces from being silently connected.
    """

    members: list[dict[str, str]] = []
    for name, member in sorted(interface.__dict__.items()):
        if name.startswith("_"):
            continue
        if isinstance(member, property):
            getter = member.fget
            signature = str(inspect.signature(getter)) if getter is not None else ""
            members.append({"name": name, "kind": "property", "signature": signature})
        elif callable(member):
            members.append(
                {
                    "name": name,
                    "kind": "callable",
                    "signature": str(inspect.signature(member)),
                }
            )
    return canonical_digest(
        {
            "module": interface.__module__,
            "qualname": interface.__qualname__,
            "members": tuple(members),
        }
    )


def _require_digest(value: str, field: str) -> None:
    if not _DIGEST.fullmatch(value):
        raise CompositionContractError(f"{field} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True, order=True)
class RequirementAddress:
    consumer: SystemIdentity
    requirement_id: str

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.requirement_id):
            raise CompositionContractError("requirement_id must be a lowercase dotted token")

    @property
    def value(self) -> str:
        return f"{self.consumer.key}:{self.requirement_id}"


@dataclass(frozen=True, slots=True)
class CapabilityOffer:
    """One provider candidate; it contains identity, never the provider object."""

    offer_id: str
    owner: SystemIdentity
    scope: ScopeIdentity
    capability: CapabilityKey
    interface_digest: str
    provider_identity: str
    configuration_digest: str
    exported_to_descendants: bool = True

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.offer_id):
            raise CompositionContractError("offer_id must be a lowercase dotted token")
        if not self.provider_identity.strip():
            raise CompositionContractError("provider_identity must be non-empty")
        _require_digest(self.interface_digest, "interface_digest")
        _require_digest(self.configuration_digest, "configuration_digest")


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    """One typed dependency declared by the consuming system."""

    address: RequirementAddress
    scope: ScopeIdentity
    capability: CapabilityKey
    interface_digest: str
    cardinality: RequirementCardinality = RequirementCardinality.EXACTLY_ONE
    optional: bool = False

    def __post_init__(self) -> None:
        _require_digest(self.interface_digest, "interface_digest")


@dataclass(frozen=True, slots=True)
class SystemCompositionContract:
    """All composition-facing offers and requirements of one system module."""

    system: SystemIdentity
    scope: ScopeIdentity
    offers: tuple[CapabilityOffer, ...] = ()
    requirements: tuple[CapabilityRequirement, ...] = ()

    def __post_init__(self) -> None:
        offer_ids = [offer.offer_id for offer in self.offers]
        if len(offer_ids) != len(set(offer_ids)):
            raise CompositionContractError(f"duplicate offer id in {self.system.key}")
        requirement_ids = [requirement.address.requirement_id for requirement in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise CompositionContractError(f"duplicate requirement id in {self.system.key}")
        for offer in self.offers:
            if offer.owner != self.system or offer.scope != self.scope:
                raise CompositionContractError("an offer must be owned at its contract system and scope")
        for requirement in self.requirements:
            if requirement.address.consumer != self.system or requirement.scope != self.scope:
                raise CompositionContractError(
                    "a requirement must be consumed at its contract system and scope"
                )


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    """Explicit provider policy when a requirement has more than one candidate."""

    requirement: RequirementAddress
    offer_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.offer_ids:
            raise CompositionContractError("provider selection must name at least one offer")
        if len(self.offer_ids) != len(set(self.offer_ids)):
            raise CompositionContractError("provider selection contains a duplicate offer")


@dataclass(frozen=True, slots=True)
class CompositionIdentity:
    """Identity of one recursive composition root and its immutable scope."""

    composition_id: str
    scope: ScopeIdentity
    owner_system: SystemIdentity | None = None
    parent_plan_digest: str | None = None

    def __post_init__(self) -> None:
        if not _TOKEN.fullmatch(self.composition_id):
            raise CompositionContractError("composition_id must be a lowercase dotted token")
        if self.parent_plan_digest is not None:
            _require_digest(self.parent_plan_digest, "parent_plan_digest")


@dataclass(frozen=True, slots=True)
class BindingEdge:
    requirement: RequirementAddress
    offer: CapabilityOffer


@dataclass(frozen=True, slots=True)
class BindingPlan:
    """Frozen, inspectable wiring evidence; it never stores runtime objects."""

    identity: CompositionIdentity
    contracts: tuple[SystemCompositionContract, ...]
    imported_offers: tuple[CapabilityOffer, ...]
    edges: tuple[BindingEdge, ...]
    digest: str

    def bindings_for(self, requirement: RequirementAddress) -> tuple[BindingEdge, ...]:
        """Return metadata for one declared requirement, never a provider instance."""

        return tuple(edge for edge in self.edges if edge.requirement == requirement)


class CapabilityCompositionPlanner:
    """Validate and freeze a recursive capability graph at composition time."""

    def __init__(self, *, systems: SystemRegistryPort, scopes: ScopeRegistryPort) -> None:
        self._systems = systems
        self._scopes = scopes

    def freeze(
        self,
        identity: CompositionIdentity,
        contracts: tuple[SystemCompositionContract, ...],
        *,
        imported_offers: tuple[CapabilityOffer, ...] = (),
        selections: tuple[ProviderSelection, ...] = (),
    ) -> BindingPlan:
        self._validate_identity(identity)
        self._validate_contracts(identity, contracts)
        offers = self._collect_offers(contracts, imported_offers)
        requirements = self._collect_requirements(contracts)
        selected = self._selection_map(requirements, selections)
        edges: list[BindingEdge] = []
        for requirement in requirements:
            candidates = self._candidates(requirement, offers)
            choices = selected.get(requirement.address)
            resolved = self._resolve_requirement(requirement, candidates, choices)
            edges.extend(BindingEdge(requirement.address, offer) for offer in resolved)
        ordered_edges = tuple(
            sorted(
                edges,
                key=lambda edge: (
                    edge.requirement.consumer.key,
                    edge.requirement.requirement_id,
                    edge.offer.offer_id,
                ),
            )
        )
        self._reject_cycles(contracts, ordered_edges)
        ordered_contracts = tuple(sorted(contracts, key=lambda contract: contract.system.key))
        ordered_imports = tuple(sorted(imported_offers, key=lambda offer: offer.offer_id))
        digest = canonical_digest(
            {
                "identity": identity,
                "contracts": ordered_contracts,
                "imports": ordered_imports,
                "edges": ordered_edges,
            }
        )
        return BindingPlan(identity, ordered_contracts, ordered_imports, ordered_edges, digest)

    def _validate_identity(self, identity: CompositionIdentity) -> None:
        if not self._scopes.contains(identity.scope):
            raise CompositionContractError(f"composition scope is not registered: {identity.scope.key}")
        if identity.owner_system is not None and not self._systems.contains(identity.owner_system.key):
            raise CompositionTopologyError(
                f"composition owner is not registered: {identity.owner_system.key}"
            )

    def _validate_contracts(
        self,
        identity: CompositionIdentity,
        contracts: tuple[SystemCompositionContract, ...],
    ) -> None:
        systems = [contract.system for contract in contracts]
        if len(systems) != len(set(systems)):
            raise CompositionContractError("a composition plan contains a duplicate system contract")
        if identity.owner_system is None:
            allowed = None
        else:
            allowed = {
                identity.owner_system,
                *(child.identity for child in self._systems.children(identity.owner_system.key)),
            }
        for contract in contracts:
            if not self._systems.contains(contract.system.key):
                raise CompositionTopologyError(f"contract system is not registered: {contract.system.key}")
            if contract.scope != identity.scope:
                raise CompositionContractError("a contract scope must equal its composition scope")
            if not self._scopes.contains(contract.scope):
                raise CompositionContractError(f"contract scope is not registered: {contract.scope.key}")
            if allowed is not None and contract.system not in allowed:
                raise CompositionTopologyError(
                    f"{identity.owner_system.key} may compose only itself or a direct child, "
                    f"not {contract.system.key}"
                )

    @staticmethod
    def _collect_offers(
        contracts: tuple[SystemCompositionContract, ...],
        imported_offers: tuple[CapabilityOffer, ...],
    ) -> tuple[CapabilityOffer, ...]:
        offers = tuple(offer for contract in contracts for offer in contract.offers) + imported_offers
        offer_ids = [offer.offer_id for offer in offers]
        if len(offer_ids) != len(set(offer_ids)):
            raise CompositionContractError("a composition plan contains a duplicate offer id")
        return tuple(sorted(offers, key=lambda offer: offer.offer_id))

    @staticmethod
    def _collect_requirements(
        contracts: tuple[SystemCompositionContract, ...],
    ) -> tuple[CapabilityRequirement, ...]:
        requirements = tuple(
            requirement for contract in contracts for requirement in contract.requirements
        )
        addresses = [requirement.address for requirement in requirements]
        if len(addresses) != len(set(addresses)):
            raise CompositionContractError("a composition plan contains a duplicate requirement address")
        return tuple(sorted(requirements, key=lambda requirement: requirement.address.value))

    @staticmethod
    def _selection_map(
        requirements: tuple[CapabilityRequirement, ...],
        selections: tuple[ProviderSelection, ...],
    ) -> dict[RequirementAddress, tuple[str, ...]]:
        known = {requirement.address for requirement in requirements}
        result: dict[RequirementAddress, tuple[str, ...]] = {}
        for selection in selections:
            if selection.requirement not in known:
                raise CompositionContractError(
                    f"selection names an unknown requirement: {selection.requirement.value}"
                )
            if selection.requirement in result:
                raise CompositionContractError(
                    f"requirement has more than one provider selection: {selection.requirement.value}"
                )
            result[selection.requirement] = tuple(sorted(selection.offer_ids))
        return result

    def _candidates(
        self,
        requirement: CapabilityRequirement,
        offers: tuple[CapabilityOffer, ...],
    ) -> tuple[CapabilityOffer, ...]:
        same_capability = tuple(
            offer for offer in offers if offer.capability == requirement.capability
        )
        same_interface = tuple(
            offer
            for offer in same_capability
            if offer.interface_digest == requirement.interface_digest
        )
        if same_capability and not same_interface:
            offered = ", ".join(sorted(offer.offer_id for offer in same_capability))
            raise CapabilityInterfaceMismatch(
                f"interface digest mismatch for {requirement.address.value}; offers={offered}"
            )
        return tuple(
            offer
            for offer in same_interface
            if self._visible_at_scope(offer, requirement.scope)
        )

    def _visible_at_scope(self, offer: CapabilityOffer, consumer_scope: ScopeIdentity) -> bool:
        if offer.scope == consumer_scope:
            return True
        if not offer.exported_to_descendants:
            return False
        return offer.scope in self._scopes.ancestry(consumer_scope)

    @staticmethod
    def _resolve_requirement(
        requirement: CapabilityRequirement,
        candidates: tuple[CapabilityOffer, ...],
        selected_ids: tuple[str, ...] | None,
    ) -> tuple[CapabilityOffer, ...]:
        candidates_by_id = {offer.offer_id: offer for offer in candidates}
        if selected_ids is not None:
            missing = tuple(offer_id for offer_id in selected_ids if offer_id not in candidates_by_id)
            if missing:
                raise CapabilityBindingError(
                    f"selection for {requirement.address.value} names ineligible offers: {', '.join(missing)}"
                )
            resolved = tuple(candidates_by_id[offer_id] for offer_id in selected_ids)
        elif len(candidates) == 1:
            resolved = candidates
        elif not candidates and requirement.optional:
            return ()
        elif not candidates:
            raise MissingCapabilityProvider(
                f"no provider for {requirement.address.value} ({requirement.capability.value})"
            )
        else:
            options = ", ".join(offer.offer_id for offer in candidates)
            raise AmbiguousCapabilityProvider(
                f"multiple providers for {requirement.address.value}: {options}; select explicitly"
            )
        if requirement.cardinality is RequirementCardinality.EXACTLY_ONE and len(resolved) != 1:
            raise CapabilityBindingError(
                f"{requirement.address.value} requires exactly one provider, got {len(resolved)}"
            )
        if requirement.cardinality is RequirementCardinality.ONE_OR_MORE and not resolved:
            if requirement.optional:
                return ()
            raise MissingCapabilityProvider(
                f"no provider for {requirement.address.value} ({requirement.capability.value})"
            )
        return resolved

    @staticmethod
    def _reject_cycles(
        contracts: tuple[SystemCompositionContract, ...],
        edges: tuple[BindingEdge, ...],
    ) -> None:
        local = {contract.system.key for contract in contracts}
        graph: dict[str, set[str]] = {system: set() for system in local}
        for edge in edges:
            consumer = edge.requirement.consumer.key
            provider = edge.offer.owner.key
            if consumer in local and provider in local and consumer != provider:
                graph[consumer].add(provider)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str, trail: tuple[str, ...]) -> None:
            if node in visiting:
                cycle = " -> ".join((*trail, node))
                raise CapabilityDependencyCycle(f"capability dependency cycle: {cycle}")
            if node in visited:
                return
            visiting.add(node)
            for target in sorted(graph[node]):
                visit(target, (*trail, node))
            visiting.remove(node)
            visited.add(node)

        for node in sorted(graph):
            visit(node, ())


__all__ = [
    "AmbiguousCapabilityProvider",
    "BindingEdge",
    "BindingPlan",
    "CapabilityBindingError",
    "CapabilityDependencyCycle",
    "CapabilityInterfaceMismatch",
    "CapabilityKey",
    "CapabilityOffer",
    "CapabilityRequirement",
    "CapabilityCompositionPlanner",
    "CompositionContractError",
    "CompositionIdentity",
    "CompositionTopologyError",
    "MissingCapabilityProvider",
    "ProviderSelection",
    "RequirementAddress",
    "RequirementCardinality",
    "SystemCompositionContract",
    "interface_contract_digest",
]
