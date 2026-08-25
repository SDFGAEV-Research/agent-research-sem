# vNext Boundary: reliability/diagnostics/timeline

SYSTEM = "reliability"
NODE = "reliability/diagnostics/timeline"
OWNS = "cross-system chronological diagnostic timelines"
MUST_NOT_OWN = "source event truth"
AUTHORITY = "diagnostic_timeline"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/diagnostics/timeline",
    package_prefix='research_platform.reliability.diagnostics.timeline',
    authority_id="diagnostic_timeline",
    owns="cross-system chronological diagnostic timelines",
    must_not_own="source event truth",
    api_module='research_platform.reliability.diagnostics.timeline.api',
    runtime_module='research_platform.reliability.diagnostics.timeline.runtime',
    provider_module='research_platform.reliability.diagnostics.timeline.providers',
    composition_module='research_platform.reliability.diagnostics.timeline.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
