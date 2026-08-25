# vNext Boundary: environment/resolution

SYSTEM = "environment"
NODE = "environment/resolution"
OWNS = "resolve logical environment requirements to concrete instance plan"
MUST_NOT_OWN = "process lifecycle"
AUTHORITY = "environment_resolution"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="environment",
    node="environment/resolution",
    package_prefix='research_platform.environment.resolution',
    authority_id="environment_resolution",
    owns="resolve logical environment requirements to concrete instance plan",
    must_not_own="process lifecycle",
    api_module='research_platform.environment.resolution.api',
    runtime_module='research_platform.environment.resolution.runtime',
    provider_module='research_platform.environment.resolution.providers',
    composition_module='research_platform.environment.resolution.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
