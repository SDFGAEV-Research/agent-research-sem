# vNext Boundary: runtime/control

SYSTEM = "runtime"
NODE = "runtime/control"
OWNS = "runtime control commands, transitions and recovery handoff"
MUST_NOT_OWN = "failure taxonomy and recovery evidence"
AUTHORITY = "runtime_control"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/control",
    package_prefix='research_platform.runtime.control',
    authority_id="runtime_control",
    owns="runtime control commands, transitions and recovery handoff",
    must_not_own="failure taxonomy and recovery evidence",
    api_module='research_platform.runtime.control.api',
    runtime_module='research_platform.runtime.control.runtime',
    provider_module='research_platform.runtime.control.providers',
    composition_module='research_platform.runtime.control.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
