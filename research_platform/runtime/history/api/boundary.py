# vNext Boundary: runtime/history

SYSTEM = "runtime"
NODE = "runtime/history"
OWNS = "runtime state/history snapshots and integrity"
MUST_NOT_OWN = "current live process truth"
AUTHORITY = "runtime_history"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/history",
    package_prefix='research_platform.runtime.history',
    authority_id="runtime_history",
    owns="runtime state/history snapshots and integrity",
    must_not_own="current live process truth",
    api_module='research_platform.runtime.history.api',
    runtime_module='research_platform.runtime.history.runtime',
    provider_module='research_platform.runtime.history.providers',
    composition_module='research_platform.runtime.history.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
