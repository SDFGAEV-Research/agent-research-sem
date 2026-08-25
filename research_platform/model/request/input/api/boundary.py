# vNext Boundary: model/request/input

SYSTEM = "model"
NODE = "model/request/input"
OWNS = "exact request input identity and canonicalization"
MUST_NOT_OWN = "serving process lifecycle"
AUTHORITY = "request_input"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="model",
    node="model/request/input",
    package_prefix='research_platform.model.request.input',
    authority_id="request_input",
    owns="exact request input identity and canonicalization",
    must_not_own="serving process lifecycle",
    api_module='research_platform.model.request.input.api',
    runtime_module='research_platform.model.request.input.runtime',
    provider_module='research_platform.model.request.input.providers',
    composition_module='research_platform.model.request.input.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
