# vNext Boundary: runtime/process/launch

SYSTEM = "runtime"
NODE = "runtime/process/launch"
OWNS = "process launch specifications and provider handoff"
MUST_NOT_OWN = "process supervision"
AUTHORITY = "process_launch"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/process/launch",
    package_prefix='research_platform.runtime.process.launch',
    authority_id="process_launch",
    owns="process launch specifications and provider handoff",
    must_not_own="process supervision",
    api_module='research_platform.runtime.process.launch.api',
    runtime_module='research_platform.runtime.process.launch.runtime',
    provider_module='research_platform.runtime.process.launch.providers',
    composition_module='research_platform.runtime.process.launch.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
