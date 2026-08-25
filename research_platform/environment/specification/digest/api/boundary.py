# vNext Boundary: environment/specification/digest

SYSTEM = "environment"
NODE = "environment/specification/digest"
OWNS = "exact environment specification identity and digest"
MUST_NOT_OWN = "resource resolution"
AUTHORITY = "environment_digest"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="environment",
    node="environment/specification/digest",
    package_prefix='research_platform.environment.specification.digest',
    authority_id="environment_digest",
    owns="exact environment specification identity and digest",
    must_not_own="resource resolution",
    api_module='research_platform.environment.specification.digest.api',
    runtime_module='research_platform.environment.specification.digest.runtime',
    provider_module='research_platform.environment.specification.digest.providers',
    composition_module='research_platform.environment.specification.digest.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
