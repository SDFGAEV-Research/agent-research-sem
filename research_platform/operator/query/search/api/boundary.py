# vNext Boundary: operator/query/search

SYSTEM = "operator"
NODE = "operator/query/search"
OWNS = "human-readable search and filtering over read-side projections"
MUST_NOT_OWN = "authoritative writes"
AUTHORITY = "operator_search"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="operator",
    node="operator/query/search",
    package_prefix='research_platform.operator.query.search',
    authority_id="operator_search",
    owns="human-readable search and filtering over read-side projections",
    must_not_own="authoritative writes",
    api_module='research_platform.operator.query.search.api',
    runtime_module='research_platform.operator.query.search.runtime',
    provider_module='research_platform.operator.query.search.providers',
    composition_module='research_platform.operator.query.search.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
