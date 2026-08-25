# vNext Boundary: environment/instance/readiness

SYSTEM = "environment"
NODE = "environment/instance/readiness"
OWNS = "environment readiness observations/contract"
MUST_NOT_OWN = "authoritative process health"
AUTHORITY = "environment_readiness"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="environment",
    node="environment/instance/readiness",
    package_prefix='research_platform.environment.instance.readiness',
    authority_id="environment_readiness",
    owns="environment readiness observations/contract",
    must_not_own="authoritative process health",
    api_module='research_platform.environment.instance.readiness.api',
    runtime_module='research_platform.environment.instance.readiness.runtime',
    provider_module='research_platform.environment.instance.readiness.providers',
    composition_module='research_platform.environment.instance.readiness.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
