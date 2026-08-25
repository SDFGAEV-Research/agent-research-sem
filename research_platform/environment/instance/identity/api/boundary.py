# vNext Boundary: environment/instance/identity

SYSTEM = "environment"
NODE = "environment/instance/identity"
OWNS = "environment instance identity and provenance"
MUST_NOT_OWN = "host process lifecycle"
AUTHORITY = "environment_instance_identity"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="environment",
    node="environment/instance/identity",
    package_prefix='research_platform.environment.instance.identity',
    authority_id="environment_instance_identity",
    owns="environment instance identity and provenance",
    must_not_own="host process lifecycle",
    api_module='research_platform.environment.instance.identity.api',
    runtime_module='research_platform.environment.instance.identity.runtime',
    provider_module='research_platform.environment.instance.identity.providers',
    composition_module='research_platform.environment.instance.identity.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
