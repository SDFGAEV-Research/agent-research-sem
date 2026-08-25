# vNext Boundary: runtime/session/binding

SYSTEM = "runtime"
NODE = "runtime/session/binding"
OWNS = "bind sessions to server/process/environment/model identities"
MUST_NOT_OWN = "provider process control"
AUTHORITY = "runtime_binding"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/session/binding",
    package_prefix='research_platform.runtime.session.binding',
    authority_id="runtime_binding",
    owns="bind sessions to server/process/environment/model identities",
    must_not_own="provider process control",
    api_module='research_platform.runtime.session.binding.api',
    runtime_module='research_platform.runtime.session.binding.runtime',
    provider_module='research_platform.runtime.session.binding.providers',
    composition_module='research_platform.runtime.session.binding.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
