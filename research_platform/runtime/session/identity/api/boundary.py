# vNext Boundary: runtime/session/identity

SYSTEM = "runtime"
NODE = "runtime/session/identity"
OWNS = "runtime session identity and frozen bindings"
MUST_NOT_OWN = "participant session semantics"
AUTHORITY = "runtime_session_identity"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="runtime",
    node="runtime/session/identity",
    package_prefix='research_platform.runtime.session.identity',
    authority_id="runtime_session_identity",
    owns="runtime session identity and frozen bindings",
    must_not_own="participant session semantics",
    api_module='research_platform.runtime.session.identity.api',
    runtime_module='research_platform.runtime.session.identity.runtime',
    provider_module='research_platform.runtime.session.identity.providers',
    composition_module='research_platform.runtime.session.identity.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
