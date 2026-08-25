# vNext Boundary: platform/configuration

SYSTEM = "platform"
NODE = "platform/configuration"
OWNS = "platform configuration sources and frozen configuration snapshots"
MUST_NOT_OWN = "domain configuration semantics"
AUTHORITY = "platform_configuration"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="platform",
    node="platform/configuration",
    package_prefix='research_platform.platform.configuration',
    authority_id="platform_configuration",
    owns="platform configuration sources and frozen configuration snapshots",
    must_not_own="domain configuration semantics",
    api_module='research_platform.platform.configuration.api',
    runtime_module='research_platform.platform.configuration.runtime',
    provider_module='research_platform.platform.configuration.providers',
    composition_module='research_platform.platform.configuration.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
