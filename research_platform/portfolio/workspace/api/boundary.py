# vNext Boundary: portfolio/workspace

SYSTEM = "portfolio"
NODE = "portfolio/workspace"
OWNS = "workspace metadata and lifecycle"
MUST_NOT_OWN = "generic scope tree authority"
AUTHORITY = "workspace_metadata"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="portfolio",
    node="portfolio/workspace",
    package_prefix='research_platform.portfolio.workspace',
    authority_id="workspace_metadata",
    owns="workspace metadata and lifecycle",
    must_not_own="generic scope tree authority",
    api_module='research_platform.portfolio.workspace.api',
    runtime_module='research_platform.portfolio.workspace.runtime',
    provider_module='research_platform.portfolio.workspace.providers',
    composition_module='research_platform.portfolio.workspace.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
