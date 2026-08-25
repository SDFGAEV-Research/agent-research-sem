# vNext Boundary: observability/logging/projection

SYSTEM = "observability"
NODE = "observability/logging/projection"
OWNS = "derived log indexes and projections"
MUST_NOT_OWN = "source log truth"
AUTHORITY = "log_projection"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/logging/projection",
    package_prefix='research_platform.observability.logging.projection',
    authority_id="log_projection",
    owns="derived log indexes and projections",
    must_not_own="source log truth",
    api_module='research_platform.observability.logging.projection.api',
    runtime_module='research_platform.observability.logging.projection.runtime',
    provider_module='research_platform.observability.logging.projection.providers',
    composition_module='research_platform.observability.logging.projection.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
