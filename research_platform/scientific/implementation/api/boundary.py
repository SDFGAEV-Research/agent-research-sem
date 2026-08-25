# vNext Boundary: scientific/implementation

SYSTEM = "scientific"
NODE = "scientific/implementation"
OWNS = "method implementation registry and provider contracts"
MUST_NOT_OWN = "method scientific truth"
AUTHORITY = "method_implementation_catalog"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="scientific",
    node="scientific/implementation",
    package_prefix='research_platform.scientific.implementation',
    authority_id="method_implementation_catalog",
    owns="method implementation registry and provider contracts",
    must_not_own="method scientific truth",
    api_module='research_platform.scientific.implementation.api',
    runtime_module='research_platform.scientific.implementation.runtime',
    provider_module='research_platform.scientific.implementation.providers',
    composition_module='research_platform.scientific.implementation.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
