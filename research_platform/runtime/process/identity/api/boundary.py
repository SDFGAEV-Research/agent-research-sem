# vNext Boundary: runtime/process/identity

SYSTEM = "runtime"
NODE = "runtime/process/identity"
OWNS = "stable process identity and launch contract identity"
MUST_NOT_OWN = "live process status"
AUTHORITY = "process_identity"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/process/identity",
    package_prefix='research_platform.runtime.process.identity',
    authority_id="process_identity",
    owns="stable process identity and launch contract identity",
    must_not_own="live process status",
    api_module='research_platform.runtime.process.identity.api',
    runtime_module='research_platform.runtime.process.identity.runtime',
    provider_module='research_platform.runtime.process.identity.providers',
    composition_module='research_platform.runtime.process.identity.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
