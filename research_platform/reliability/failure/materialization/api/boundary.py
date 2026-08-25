# vNext Boundary: reliability/failure/materialization

SYSTEM = "reliability"
NODE = "reliability/failure/materialization"
OWNS = "turn runtime exceptions into durable failure facts"
MUST_NOT_OWN = "exception capture itself"
AUTHORITY = "failure_materialization"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/failure/materialization",
    package_prefix='research_platform.reliability.failure.materialization',
    authority_id="failure_materialization",
    owns="turn runtime exceptions into durable failure facts",
    must_not_own="exception capture itself",
    api_module='research_platform.reliability.failure.materialization.api',
    runtime_module='research_platform.reliability.failure.materialization.runtime',
    provider_module='research_platform.reliability.failure.materialization.providers',
    composition_module='research_platform.reliability.failure.materialization.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
