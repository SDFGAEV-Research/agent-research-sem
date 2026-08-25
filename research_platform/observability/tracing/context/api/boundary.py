# vNext Boundary: observability/tracing/context

SYSTEM = "observability"
NODE = "observability/tracing/context"
OWNS = "trace/span context creation and attachment"
MUST_NOT_OWN = "business operation state"
AUTHORITY = "trace_context"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/tracing/context",
    package_prefix='research_platform.observability.tracing.context',
    authority_id="trace_context",
    owns="trace/span context creation and attachment",
    must_not_own="business operation state",
    api_module='research_platform.observability.tracing.context.api',
    runtime_module='research_platform.observability.tracing.context.runtime',
    provider_module='research_platform.observability.tracing.context.providers',
    composition_module='research_platform.observability.tracing.context.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
