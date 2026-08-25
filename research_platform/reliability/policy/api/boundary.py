# vNext Boundary: reliability/policy

SYSTEM = "reliability"
NODE = "reliability/policy"
OWNS = "reliability invariants, no-fallback rules and escalation policies"
MUST_NOT_OWN = "runtime implementation"
AUTHORITY = "reliability_policy"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/policy",
    package_prefix='research_platform.reliability.policy',
    authority_id="reliability_policy",
    owns="reliability invariants, no-fallback rules and escalation policies",
    must_not_own="runtime implementation",
    api_module='research_platform.reliability.policy.api',
    runtime_module='research_platform.reliability.policy.runtime',
    provider_module='research_platform.reliability.policy.providers',
    composition_module='research_platform.reliability.policy.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
