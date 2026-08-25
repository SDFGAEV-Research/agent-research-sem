# vNext Boundary: portfolio/program

SYSTEM = "portfolio"
NODE = "portfolio/program"
OWNS = "research program metadata and project grouping"
MUST_NOT_OWN = "study semantics"
AUTHORITY = "program_metadata"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="portfolio",
    node="portfolio/program",
    package_prefix='research_platform.portfolio.program',
    authority_id="program_metadata",
    owns="research program metadata and project grouping",
    must_not_own="study semantics",
    api_module='research_platform.portfolio.program.api',
    runtime_module='research_platform.portfolio.program.runtime',
    provider_module='research_platform.portfolio.program.providers',
    composition_module='research_platform.portfolio.program.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
