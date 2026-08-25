# vNext Boundary: scientific/method

SYSTEM = "scientific"
NODE = "scientific/method"
OWNS = "method identity, configuration and lifecycle"
MUST_NOT_OWN = "runtime session internals"
AUTHORITY = "method_identity"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="scientific",
    node="scientific/method",
    package_prefix='research_platform.scientific.method',
    authority_id="method_identity",
    owns="method identity, configuration and lifecycle",
    must_not_own="runtime session internals",
    api_module='research_platform.scientific.method.api',
    runtime_module='research_platform.scientific.method.runtime',
    provider_module='research_platform.scientific.method.providers',
    composition_module='research_platform.scientific.method.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
