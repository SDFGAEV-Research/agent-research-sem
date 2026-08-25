# vNext Boundary: runtime/supervision

SYSTEM = "runtime"
NODE = "runtime/supervision"
OWNS = "supervision loops, health checks and restart/reconcile orchestration"
MUST_NOT_OWN = "diagnostic storage and failure taxonomy"
AUTHORITY = "supervision_state"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/supervision",
    package_prefix='research_platform.runtime.supervision',
    authority_id="supervision_state",
    owns="supervision loops, health checks and restart/reconcile orchestration",
    must_not_own="diagnostic storage and failure taxonomy",
    api_module='research_platform.runtime.supervision.api',
    runtime_module='research_platform.runtime.supervision.runtime',
    provider_module='research_platform.runtime.supervision.providers',
    composition_module='research_platform.runtime.supervision.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
