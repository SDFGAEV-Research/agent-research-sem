# vNext Boundary: reliability/reconciliation/effect

SYSTEM = "reliability"
NODE = "reliability/reconciliation/effect"
OWNS = "reconcile uncertain external effects"
MUST_NOT_OWN = "business state authority"
AUTHORITY = "effect_reconciliation"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/reconciliation/effect",
    package_prefix='research_platform.reliability.reconciliation.effect',
    authority_id="effect_reconciliation",
    owns="reconcile uncertain external effects",
    must_not_own="business state authority",
    api_module='research_platform.reliability.reconciliation.effect.api',
    runtime_module='research_platform.reliability.reconciliation.effect.runtime',
    provider_module='research_platform.reliability.reconciliation.effect.providers',
    composition_module='research_platform.reliability.reconciliation.effect.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
