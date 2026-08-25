# vNext Boundary: reliability/incident

SYSTEM = "reliability"
NODE = "reliability/incident"
OWNS = "incident grouping, lifecycle and incident identity"
MUST_NOT_OWN = "raw failure taxonomy"
AUTHORITY = "incident_authority"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/incident",
    package_prefix='research_platform.reliability.incident',
    authority_id="incident_authority",
    owns="incident grouping, lifecycle and incident identity",
    must_not_own="raw failure taxonomy",
    api_module='research_platform.reliability.incident.api',
    runtime_module='research_platform.reliability.incident.runtime',
    provider_module='research_platform.reliability.incident.providers',
    composition_module='research_platform.reliability.incident.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
