# vNext Boundary: data/query/cross

SYSTEM = "data"
NODE = "data/query/cross"
OWNS = "cross-authority read composition and query federation"
MUST_NOT_OWN = "writes and authority mutation"
AUTHORITY = "cross_query"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="data",
    node="data/query/cross",
    package_prefix='research_platform.data.query.cross',
    authority_id="cross_query",
    owns="cross-authority read composition and query federation",
    must_not_own="writes and authority mutation",
    api_module='research_platform.data.query.cross.api',
    runtime_module='research_platform.data.query.cross.runtime',
    provider_module='research_platform.data.query.cross.providers',
    composition_module='research_platform.data.query.cross.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
