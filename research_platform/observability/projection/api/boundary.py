# vNext Boundary: observability/projection

SYSTEM = "observability"
NODE = "observability/projection"
OWNS = "observation projections/indexes and read models"
MUST_NOT_OWN = "source-of-truth mutation"
AUTHORITY = "observation_projection"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/projection",
    package_prefix='research_platform.observability.projection',
    authority_id="observation_projection",
    owns="observation projections/indexes and read models",
    must_not_own="source-of-truth mutation",
    api_module='research_platform.observability.projection.api',
    runtime_module='research_platform.observability.projection.runtime',
    provider_module='research_platform.observability.projection.providers',
    composition_module='research_platform.observability.projection.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
