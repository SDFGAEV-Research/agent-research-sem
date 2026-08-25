# vNext Boundary: execution/operation

SYSTEM = "execution"
NODE = "execution/operation"
OWNS = "operation identity, lifecycle and result envelopes"
MUST_NOT_OWN = "failure taxonomy and recovery authority"
AUTHORITY = "operation_state"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="execution",
    node="execution/operation",
    package_prefix='research_platform.execution.operation',
    authority_id="operation_state",
    owns="operation identity, lifecycle and result envelopes",
    must_not_own="failure taxonomy and recovery authority",
    api_module='research_platform.execution.operation.api',
    runtime_module='research_platform.execution.operation.runtime',
    provider_module='research_platform.execution.operation.providers',
    composition_module='research_platform.execution.operation.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
