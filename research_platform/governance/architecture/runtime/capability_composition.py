"""Concrete validation for typed composition plans.

Only composition roots import this implementation. Projects receive the
``CapabilityCompositionPlannerPort`` declared by the architecture API.
"""

from __future__ import annotations

from research_platform.governance.architecture.api.capability_composition import (
    AmbiguousCapabilityProvider,
    BindingEdge,
    BindingPlan,
    CapabilityBindingError,
    CapabilityCompositionPlannerPort,
    CapabilityDependencyCycle,
    CapabilityInterfaceMismatch,
    CapabilityOffer,
    CapabilityRequirement,
    CompositionContract,
    CompositionContractError,
    CompositionIdentity,
    CompositionSubject,
    CompositionSubjectKind,
    CompositionTopologyError,
    MissingCapabilityProvider,
    ProviderSelection,
    RequirementAddress,
)
from research_platform.governance.system_registry.api import SystemRegistryPort
from research_platform.platform.kernel import canonical_digest
from research_platform.scope.api import ScopeIdentity, ScopeRegistryPort


class CapabilityCompositionPlanner(CapabilityCompositionPlannerPort):
    """Validate and freeze a recursive capability graph at composition time."""

    def __init__(self, *, systems: SystemRegistryPort, scopes: ScopeRegistryPort) -> None:
        self._systems = systems
        self._scopes = scopes

    def freeze(
        self,
        identity: CompositionIdentity,
        contracts: tuple[CompositionContract, ...],
        *,
        imported_offers: tuple[CapabilityOffer, ...] = (),
        selections: tuple[ProviderSelection, ...] = (),
    ) -> BindingPlan:
        self._validate_identity(identity)
        self._validate_contracts(identity, contracts)
        self._validate_imported_offers(identity, imported_offers)
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
        ordered_contracts = tuple(sorted(contracts, key=lambda contract: contract.subject.key))
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
        if identity.owner.kind is CompositionSubjectKind.SYSTEM and (
            identity.owner.system is None or not self._systems.contains(identity.owner.system.key)
        ):
            raise CompositionTopologyError(
                f"composition owner is not registered: {identity.owner.subject_id}"
            )

    def _validate_contracts(
        self,
        identity: CompositionIdentity,
        contracts: tuple[CompositionContract, ...],
    ) -> None:
        subjects = [contract.subject for contract in contracts]
        if len(subjects) != len(set(subjects)):
            raise CompositionContractError("a composition plan contains a duplicate subject contract")
        if identity.owner.kind is CompositionSubjectKind.PROJECT:
            allowed = {identity.owner}
        else:
            assert identity.owner.system is not None
            allowed = {
                identity.owner,
                *(
                    CompositionSubject.system_subject(child.identity)
                    for child in self._systems.children(identity.owner.system.key)
                ),
            }
        for contract in contracts:
            if (
                contract.subject.kind is CompositionSubjectKind.SYSTEM
                and (
                    contract.subject.system is None
                    or not self._systems.contains(contract.subject.system.key)
                )
            ):
                raise CompositionTopologyError(
                    f"contract system is not registered: {contract.subject.subject_id}"
                )
            if contract.scope != identity.scope:
                raise CompositionContractError("a contract scope must equal its composition scope")
            if not self._scopes.contains(contract.scope):
                raise CompositionContractError(f"contract scope is not registered: {contract.scope.key}")
            if contract.subject not in allowed:
                owner = identity.owner.key
                raise CompositionTopologyError(
                    f"{owner} may compose only its local subject boundary, "
                    f"not {contract.subject.key}"
                )

    def _validate_imported_offers(
        self,
        identity: CompositionIdentity,
        imported_offers: tuple[CapabilityOffer, ...],
    ) -> None:
        """Imported boundaries must name a real external system authority.

        A local project can publish a project-owned offer inside its own
        contract, but it may not import a second project's binding and thereby
        create an undeclared project-to-project composition hierarchy.
        """

        for offer in imported_offers:
            if not self._scopes.contains(offer.scope):
                raise CompositionContractError(
                    f"imported offer scope is not registered: {offer.scope.key}"
                )
            if offer.owner.kind is CompositionSubjectKind.PROJECT:
                raise CompositionTopologyError(
                    f"{identity.owner.key} cannot import project-owned offer {offer.offer_id}; "
                    "project-local offers belong in the owning project contract"
                )
            if offer.owner.system is None or not self._systems.contains(offer.owner.system.key):
                raise CompositionTopologyError(
                    f"imported offer owner is not a registered system: {offer.owner.subject_id}"
                )

    @staticmethod
    def _collect_offers(
        contracts: tuple[CompositionContract, ...],
        imported_offers: tuple[CapabilityOffer, ...],
    ) -> tuple[CapabilityOffer, ...]:
        offers = tuple(offer for contract in contracts for offer in contract.offers) + imported_offers
        offer_ids = [offer.offer_id for offer in offers]
        if len(offer_ids) != len(set(offer_ids)):
            raise CompositionContractError("a composition plan contains a duplicate offer id")
        return tuple(sorted(offers, key=lambda offer: offer.offer_id))

    @staticmethod
    def _collect_requirements(
        contracts: tuple[CompositionContract, ...],
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
        same_capability = tuple(offer for offer in offers if offer.capability == requirement.capability)
        same_interface = tuple(
            offer for offer in same_capability if offer.interface_digest == requirement.interface_digest
        )
        if same_capability and not same_interface:
            offered = ", ".join(sorted(offer.offer_id for offer in same_capability))
            raise CapabilityInterfaceMismatch(
                f"interface digest mismatch for {requirement.address.value}; offers={offered}"
            )
        return tuple(
            offer for offer in same_interface if self._visible_at_scope(offer, requirement.scope)
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
        if requirement.cardinality.value == "exactly_one" and len(resolved) != 1:
            raise CapabilityBindingError(
                f"{requirement.address.value} requires exactly one provider, got {len(resolved)}"
            )
        if requirement.cardinality.value == "one_or_more" and not resolved:
            if requirement.optional:
                return ()
            raise MissingCapabilityProvider(
                f"no provider for {requirement.address.value} ({requirement.capability.value})"
            )
        return resolved

    @staticmethod
    def _reject_cycles(
        contracts: tuple[CompositionContract, ...],
        edges: tuple[BindingEdge, ...],
    ) -> None:
        local = {contract.subject.key for contract in contracts}
        graph: dict[str, set[str]] = {subject: set() for subject in local}
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


__all__ = ["CapabilityCompositionPlanner"]
