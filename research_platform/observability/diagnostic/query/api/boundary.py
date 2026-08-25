# vNext Boundary: observability/diagnostic/query

SYSTEM = "observability"
NODE = "observability/diagnostic/query"
OWNS = "operator/debug query language over observation sources"
MUST_NOT_OWN = "source mutation"
AUTHORITY = "diagnostic_query"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/diagnostic/query",
    package_prefix='research_platform.observability.diagnostic.query',
    authority_id="diagnostic_query",
    owns="operator/debug query language over observation sources",
    must_not_own="source mutation",
    api_module='research_platform.observability.diagnostic.query.api',
    runtime_module='research_platform.observability.diagnostic.query.runtime',
    provider_module='research_platform.observability.diagnostic.query.providers',
    composition_module='research_platform.observability.diagnostic.query.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
