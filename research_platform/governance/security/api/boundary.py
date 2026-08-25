# vNext Boundary: governance/security

SYSTEM = "governance"
NODE = "governance/security"
OWNS = "security/redaction/classification policy"
MUST_NOT_OWN = "scientific method semantics"
AUTHORITY = "security_policy"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="governance",
    node="governance/security",
    package_prefix='research_platform.governance.security',
    authority_id="security_policy",
    owns="security/redaction/classification policy",
    must_not_own="scientific method semantics",
    api_module='research_platform.governance.security.api',
    runtime_module='research_platform.governance.security.runtime',
    provider_module='research_platform.governance.security.providers',
    composition_module='research_platform.governance.security.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
