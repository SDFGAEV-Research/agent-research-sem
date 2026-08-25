# vNext Boundary: scope/resolution

SYSTEM = "scope"
NODE = "scope/resolution"
OWNS = "resolve a scope reference to canonical scope path"
MUST_NOT_OWN = "domain-specific lookup semantics"
AUTHORITY = "scope_resolution"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="scope",
    node="scope/resolution",
    package_prefix='research_platform.scope.resolution',
    authority_id="scope_resolution",
    owns="resolve a scope reference to canonical scope path",
    must_not_own="domain-specific lookup semantics",
    api_module='research_platform.scope.resolution.api',
    runtime_module='research_platform.scope.resolution.runtime',
    provider_module='research_platform.scope.resolution.providers',
    composition_module='research_platform.scope.resolution.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
