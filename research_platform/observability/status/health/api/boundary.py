# vNext Boundary: observability/status/health

SYSTEM = "observability"
NODE = "observability/status/health"
OWNS = "health observations and health snapshots"
MUST_NOT_OWN = "authoritative lifecycle transitions"
AUTHORITY = "health_observation"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/status/health",
    package_prefix='research_platform.observability.status.health',
    authority_id="health_observation",
    owns="health observations and health snapshots",
    must_not_own="authoritative lifecycle transitions",
    api_module='research_platform.observability.status.health.api',
    runtime_module='research_platform.observability.status.health.runtime',
    provider_module='research_platform.observability.status.health.providers',
    composition_module='research_platform.observability.status.health.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
