# vNext Boundary: environment/binding

SYSTEM = "environment"
NODE = "environment/binding"
OWNS = "binding environment specs to scopes/runs/participants"
MUST_NOT_OWN = "artifact storage"
AUTHORITY = "environment_binding"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="environment",
    node="environment/binding",
    package_prefix='research_platform.environment.binding',
    authority_id="environment_binding",
    owns="binding environment specs to scopes/runs/participants",
    must_not_own="artifact storage",
    api_module='research_platform.environment.binding.api',
    runtime_module='research_platform.environment.binding.runtime',
    provider_module='research_platform.environment.binding.providers',
    composition_module='research_platform.environment.binding.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
