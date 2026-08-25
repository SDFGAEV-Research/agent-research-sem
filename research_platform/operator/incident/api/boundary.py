# vNext Boundary: operator/incident

SYSTEM = "operator"
NODE = "operator/incident"
OWNS = "incident triage and incident work surfaces"
MUST_NOT_OWN = "incident authority"
AUTHORITY = "operator_incident_view"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="operator",
    node="operator/incident",
    package_prefix='research_platform.operator.incident',
    authority_id="operator_incident_view",
    owns="incident triage and incident work surfaces",
    must_not_own="incident authority",
    api_module='research_platform.operator.incident.api',
    runtime_module='research_platform.operator.incident.runtime',
    provider_module='research_platform.operator.incident.providers',
    composition_module='research_platform.operator.incident.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
