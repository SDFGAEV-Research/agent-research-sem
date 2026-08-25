# vNext Boundary: execution/scheduling

SYSTEM = "execution"
NODE = "execution/scheduling"
OWNS = "scheduling decisions and admission requests"
MUST_NOT_OWN = "live resource state"
AUTHORITY = "schedule_intent"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="execution",
    node="execution/scheduling",
    package_prefix='research_platform.execution.scheduling',
    authority_id="schedule_intent",
    owns="scheduling decisions and admission requests",
    must_not_own="live resource state",
    api_module='research_platform.execution.scheduling.api',
    runtime_module='research_platform.execution.scheduling.runtime',
    provider_module='research_platform.execution.scheduling.providers',
    composition_module='research_platform.execution.scheduling.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
