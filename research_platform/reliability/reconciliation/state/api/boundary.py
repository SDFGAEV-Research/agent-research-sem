# vNext Boundary: reliability/reconciliation/state

SYSTEM = "reliability"
NODE = "reliability/reconciliation/state"
OWNS = "reconcile uncertain durable state"
MUST_NOT_OWN = "external effect certainty"
AUTHORITY = "state_reconciliation"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/reconciliation/state",
    package_prefix='research_platform.reliability.reconciliation.state',
    authority_id="state_reconciliation",
    owns="reconcile uncertain durable state",
    must_not_own="external effect certainty",
    api_module='research_platform.reliability.reconciliation.state.api',
    runtime_module='research_platform.reliability.reconciliation.state.runtime',
    provider_module='research_platform.reliability.reconciliation.state.providers',
    composition_module='research_platform.reliability.reconciliation.state.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
