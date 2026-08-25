# vNext Boundary: environment/specification/schema

SYSTEM = "environment"
NODE = "environment/specification/schema"
OWNS = "environment requirement schema and canonical forms"
MUST_NOT_OWN = "environment instance lifecycle"
AUTHORITY = "environment_schema"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="environment",
    node="environment/specification/schema",
    package_prefix='research_platform.environment.specification.schema',
    authority_id="environment_schema",
    owns="environment requirement schema and canonical forms",
    must_not_own="environment instance lifecycle",
    api_module='research_platform.environment.specification.schema.api',
    runtime_module='research_platform.environment.specification.schema.runtime',
    provider_module='research_platform.environment.specification.schema.providers',
    composition_module='research_platform.environment.specification.schema.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
