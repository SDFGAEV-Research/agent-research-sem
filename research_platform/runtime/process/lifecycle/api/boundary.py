# vNext Boundary: runtime/process/lifecycle

SYSTEM = "runtime"
NODE = "runtime/process/lifecycle"
OWNS = "process lifecycle and termination semantics"
MUST_NOT_OWN = "failure classification"
AUTHORITY = "process_lifecycle"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/process/lifecycle",
    package_prefix='research_platform.runtime.process.lifecycle',
    authority_id="process_lifecycle",
    owns="process lifecycle and termination semantics",
    must_not_own="failure classification",
    api_module='research_platform.runtime.process.lifecycle.api',
    runtime_module='research_platform.runtime.process.lifecycle.runtime',
    provider_module='research_platform.runtime.process.lifecycle.providers',
    composition_module='research_platform.runtime.process.lifecycle.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
