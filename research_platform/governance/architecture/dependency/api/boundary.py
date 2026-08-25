# vNext Boundary: governance/architecture/dependency

SYSTEM = "governance"
NODE = "governance/architecture/dependency"
OWNS = "allowed dependency graph and import ownership rules"
MUST_NOT_OWN = "runtime behavior"
AUTHORITY = "dependency_policy"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="governance",
    node="governance/architecture/dependency",
    package_prefix='research_platform.governance.architecture.dependency',
    authority_id="dependency_policy",
    owns="allowed dependency graph and import ownership rules",
    must_not_own="runtime behavior",
    api_module='research_platform.governance.architecture.dependency.api',
    runtime_module='research_platform.governance.architecture.dependency.runtime',
    provider_module='research_platform.governance.architecture.dependency.providers',
    composition_module='research_platform.governance.architecture.dependency.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
