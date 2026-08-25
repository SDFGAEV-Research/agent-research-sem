# vNext Boundary: reliability/failure/taxonomy

SYSTEM = "reliability"
NODE = "reliability/failure/taxonomy"
OWNS = "stable failure domains and codes"
MUST_NOT_OWN = "runtime exception details"
AUTHORITY = "failure_taxonomy"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/failure/taxonomy",
    package_prefix='research_platform.reliability.failure.taxonomy',
    authority_id="failure_taxonomy",
    owns="stable failure domains and codes",
    must_not_own="runtime exception details",
    api_module='research_platform.reliability.failure.taxonomy.api',
    runtime_module='research_platform.reliability.failure.taxonomy.runtime',
    provider_module='research_platform.reliability.failure.taxonomy.providers',
    composition_module='research_platform.reliability.failure.taxonomy.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
