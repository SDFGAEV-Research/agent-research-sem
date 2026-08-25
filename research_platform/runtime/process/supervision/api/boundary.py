# vNext Boundary: runtime/process/supervision

SYSTEM = "runtime"
NODE = "runtime/process/supervision"
OWNS = "process health/reconcile loops"
MUST_NOT_OWN = "durable runtime history storage"
AUTHORITY = "process_supervision"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/process/supervision",
    package_prefix='research_platform.runtime.process.supervision',
    authority_id="process_supervision",
    owns="process health/reconcile loops",
    must_not_own="durable runtime history storage",
    api_module='research_platform.runtime.process.supervision.api',
    runtime_module='research_platform.runtime.process.supervision.runtime',
    provider_module='research_platform.runtime.process.supervision.providers',
    composition_module='research_platform.runtime.process.supervision.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
