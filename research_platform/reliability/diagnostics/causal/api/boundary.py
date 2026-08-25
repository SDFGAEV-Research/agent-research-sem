# vNext Boundary: reliability/diagnostics/causal

SYSTEM = "reliability"
NODE = "reliability/diagnostics/causal"
OWNS = "causal graph assembly from authoritative references"
MUST_NOT_OWN = "failure/effect mutation"
AUTHORITY = "causal_diagnostics"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/diagnostics/causal",
    package_prefix='research_platform.reliability.diagnostics.causal',
    authority_id="causal_diagnostics",
    owns="causal graph assembly from authoritative references",
    must_not_own="failure/effect mutation",
    api_module='research_platform.reliability.diagnostics.causal.api',
    runtime_module='research_platform.reliability.diagnostics.causal.runtime',
    provider_module='research_platform.reliability.diagnostics.causal.providers',
    composition_module='research_platform.reliability.diagnostics.causal.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
