# vNext Boundary: governance/schema

SYSTEM = "governance"
NODE = "governance/schema"
OWNS = "schema/version declarations for contracts and records"
MUST_NOT_OWN = "domain state mutation"
AUTHORITY = "schema_authority"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="governance",
    node="governance/schema",
    package_prefix='research_platform.governance.schema',
    authority_id="schema_authority",
    owns="schema/version declarations for contracts and records",
    must_not_own="domain state mutation",
    api_module='research_platform.governance.schema.api',
    runtime_module='research_platform.governance.schema.runtime',
    provider_module='research_platform.governance.schema.providers',
    composition_module='research_platform.governance.schema.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
