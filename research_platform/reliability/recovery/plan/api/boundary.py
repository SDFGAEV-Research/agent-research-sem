# vNext Boundary: reliability/recovery/plan

SYSTEM = "reliability"
NODE = "reliability/recovery/plan"
OWNS = "immutable recovery plans and exact recovery intents"
MUST_NOT_OWN = "execution of recovery effects"
AUTHORITY = "recovery_plan"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/recovery/plan",
    package_prefix='research_platform.reliability.recovery.plan',
    authority_id="recovery_plan",
    owns="immutable recovery plans and exact recovery intents",
    must_not_own="execution of recovery effects",
    api_module='research_platform.reliability.recovery.plan.api',
    runtime_module='research_platform.reliability.recovery.plan.runtime',
    provider_module='research_platform.reliability.recovery.plan.providers',
    composition_module='research_platform.reliability.recovery.plan.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
