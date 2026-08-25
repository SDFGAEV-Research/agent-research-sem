# vNext Boundary: model/request/output

SYSTEM = "model"
NODE = "model/request/output"
OWNS = "response envelope and response artifact references"
MUST_NOT_OWN = "business metric semantics"
AUTHORITY = "request_output"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="model",
    node="model/request/output",
    package_prefix='research_platform.model.request.output',
    authority_id="request_output",
    owns="response envelope and response artifact references",
    must_not_own="business metric semantics",
    api_module='research_platform.model.request.output.api',
    runtime_module='research_platform.model.request.output.runtime',
    provider_module='research_platform.model.request.output.providers',
    composition_module='research_platform.model.request.output.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
