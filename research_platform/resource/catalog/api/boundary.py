# vNext Boundary: resource/catalog

SYSTEM = "resource"
NODE = "resource/catalog"
OWNS = "resource identities/types and catalog metadata"
MUST_NOT_OWN = "live capacity"
AUTHORITY = "resource_catalog"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="resource",
    node="resource/catalog",
    package_prefix='research_platform.resource.catalog',
    authority_id="resource_catalog",
    owns="resource identities/types and catalog metadata",
    must_not_own="live capacity",
    api_module='research_platform.resource.catalog.api',
    runtime_module='research_platform.resource.catalog.runtime',
    provider_module='research_platform.resource.catalog.providers',
    composition_module='research_platform.resource.catalog.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
