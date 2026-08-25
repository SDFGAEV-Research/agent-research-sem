# vNext Boundary: governance/architecture/authority

SYSTEM = "governance"
NODE = "governance/architecture/authority"
OWNS = "authority uniqueness and boundary policy"
MUST_NOT_OWN = "authority mutation"
AUTHORITY = "authority_policy"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="governance",
    node="governance/architecture/authority",
    package_prefix='research_platform.governance.architecture.authority',
    authority_id="authority_policy",
    owns="authority uniqueness and boundary policy",
    must_not_own="authority mutation",
    api_module='research_platform.governance.architecture.authority.api',
    runtime_module='research_platform.governance.architecture.authority.runtime',
    provider_module='research_platform.governance.architecture.authority.providers',
    composition_module='research_platform.governance.architecture.authority.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
