# vNext Boundary: scope/hierarchy

SYSTEM = "scope"
NODE = "scope/hierarchy"
OWNS = "parent/child relationships, ancestry, descendants"
MUST_NOT_OWN = "project business fields"
AUTHORITY = "scope_hierarchy"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="scope",
    node="scope/hierarchy",
    package_prefix='research_platform.scope.hierarchy',
    authority_id="scope_hierarchy",
    owns="parent/child relationships, ancestry, descendants",
    must_not_own="project business fields",
    api_module='research_platform.scope.hierarchy.api',
    runtime_module='research_platform.scope.hierarchy.runtime',
    provider_module='research_platform.scope.hierarchy.providers',
    composition_module='research_platform.scope.hierarchy.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
