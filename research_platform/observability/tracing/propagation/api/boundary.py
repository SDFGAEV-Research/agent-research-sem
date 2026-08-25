# vNext Boundary: observability/tracing/propagation

SYSTEM = "observability"
NODE = "observability/tracing/propagation"
OWNS = "cross-process trace propagation contracts"
MUST_NOT_OWN = "trace storage"
AUTHORITY = "trace_propagation"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/tracing/propagation",
    package_prefix='research_platform.observability.tracing.propagation',
    authority_id="trace_propagation",
    owns="cross-process trace propagation contracts",
    must_not_own="trace storage",
    api_module='research_platform.observability.tracing.propagation.api',
    runtime_module='research_platform.observability.tracing.propagation.runtime',
    provider_module='research_platform.observability.tracing.propagation.providers',
    composition_module='research_platform.observability.tracing.propagation.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
