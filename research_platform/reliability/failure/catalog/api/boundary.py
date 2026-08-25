# vNext Boundary: reliability/failure/catalog

SYSTEM = "reliability"
NODE = "reliability/failure/catalog"
OWNS = "versioned failure catalog and semantic drift detection"
MUST_NOT_OWN = "incident state"
AUTHORITY = "failure_catalog"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/failure/catalog",
    package_prefix='research_platform.reliability.failure.catalog',
    authority_id="failure_catalog",
    owns="versioned failure catalog and semantic drift detection",
    must_not_own="incident state",
    api_module='research_platform.reliability.failure.catalog.api',
    runtime_module='research_platform.reliability.failure.catalog.runtime',
    provider_module='research_platform.reliability.failure.catalog.providers',
    composition_module='research_platform.reliability.failure.catalog.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
