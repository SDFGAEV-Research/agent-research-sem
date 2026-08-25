# vNext Boundary: platform/identity

SYSTEM = "platform"
NODE = "platform/identity"
OWNS = "platform identity and immutable platform metadata"
MUST_NOT_OWN = "workspace/project/run identity"
AUTHORITY = "platform_identity"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="platform",
    node="platform/identity",
    package_prefix='research_platform.platform.identity',
    authority_id="platform_identity",
    owns="platform identity and immutable platform metadata",
    must_not_own="workspace/project/run identity",
    api_module='research_platform.platform.identity.api',
    runtime_module='research_platform.platform.identity.runtime',
    provider_module='research_platform.platform.identity.providers',
    composition_module='research_platform.platform.identity.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
