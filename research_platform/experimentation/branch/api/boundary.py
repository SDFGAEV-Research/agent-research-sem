# vNext Boundary: experimentation/branch

SYSTEM = "experimentation"
NODE = "experimentation/branch"
OWNS = "run branching and branch lineage"
MUST_NOT_OWN = "generic artifact lineage"
AUTHORITY = "branch_state"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="experimentation",
    node="experimentation/branch",
    package_prefix='research_platform.experimentation.branch',
    authority_id="branch_state",
    owns="run branching and branch lineage",
    must_not_own="generic artifact lineage",
    api_module='research_platform.experimentation.branch.api',
    runtime_module='research_platform.experimentation.branch.runtime',
    provider_module='research_platform.experimentation.branch.providers',
    composition_module='research_platform.experimentation.branch.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
