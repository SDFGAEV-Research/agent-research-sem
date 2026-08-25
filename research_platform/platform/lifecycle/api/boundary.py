# vNext Boundary: platform/lifecycle

SYSTEM = "platform"
NODE = "platform/lifecycle"
OWNS = "platform startup/shutdown/readiness semantics"
MUST_NOT_OWN = "service/process lifecycle"
AUTHORITY = "platform_lifecycle"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="platform",
    node="platform/lifecycle",
    package_prefix='research_platform.platform.lifecycle',
    authority_id="platform_lifecycle",
    owns="platform startup/shutdown/readiness semantics",
    must_not_own="service/process lifecycle",
    api_module='research_platform.platform.lifecycle.api',
    runtime_module='research_platform.platform.lifecycle.runtime',
    provider_module='research_platform.platform.lifecycle.providers',
    composition_module='research_platform.platform.lifecycle.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
