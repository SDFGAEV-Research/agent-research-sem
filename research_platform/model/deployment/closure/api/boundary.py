# vNext Boundary: model/deployment/closure

SYSTEM = "model"
NODE = "model/deployment/closure"
OWNS = "exact deployment closure across model, stack, runtime and artifact identities"
MUST_NOT_OWN = "server runtime health"
AUTHORITY = "deployment_closure"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="model",
    node="model/deployment/closure",
    package_prefix='research_platform.model.deployment.closure',
    authority_id="deployment_closure",
    owns="exact deployment closure across model, stack, runtime and artifact identities",
    must_not_own="server runtime health",
    api_module='research_platform.model.deployment.closure.api',
    runtime_module='research_platform.model.deployment.closure.runtime',
    provider_module='research_platform.model.deployment.closure.providers',
    composition_module='research_platform.model.deployment.closure.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
