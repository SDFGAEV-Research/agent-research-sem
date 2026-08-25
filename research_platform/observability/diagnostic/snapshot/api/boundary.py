# vNext Boundary: observability/diagnostic/snapshot

SYSTEM = "observability"
NODE = "observability/diagnostic/snapshot"
OWNS = "portable diagnostic snapshots assembled from existing authorities"
MUST_NOT_OWN = "new business truth"
AUTHORITY = "diagnostic_snapshot"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/diagnostic/snapshot",
    package_prefix='research_platform.observability.diagnostic.snapshot',
    authority_id="diagnostic_snapshot",
    owns="portable diagnostic snapshots assembled from existing authorities",
    must_not_own="new business truth",
    api_module='research_platform.observability.diagnostic.snapshot.api',
    runtime_module='research_platform.observability.diagnostic.snapshot.runtime',
    provider_module='research_platform.observability.diagnostic.snapshot.providers',
    composition_module='research_platform.observability.diagnostic.snapshot.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
