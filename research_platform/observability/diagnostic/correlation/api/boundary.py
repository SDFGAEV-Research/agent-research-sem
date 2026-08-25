# vNext Boundary: observability/diagnostic/correlation

SYSTEM = "observability"
NODE = "observability/diagnostic/correlation"
OWNS = "cross-system correlation graph for diagnostic references"
MUST_NOT_OWN = "causal authority"
AUTHORITY = "diagnostic_correlation"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/diagnostic/correlation",
    package_prefix='research_platform.observability.diagnostic.correlation',
    authority_id="diagnostic_correlation",
    owns="cross-system correlation graph for diagnostic references",
    must_not_own="causal authority",
    api_module='research_platform.observability.diagnostic.correlation.api',
    runtime_module='research_platform.observability.diagnostic.correlation.runtime',
    provider_module='research_platform.observability.diagnostic.correlation.providers',
    composition_module='research_platform.observability.diagnostic.correlation.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
