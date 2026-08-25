# vNext Boundary: scientific/protocol

SYSTEM = "scientific"
NODE = "scientific/protocol"
OWNS = "scientific protocol definitions and execution constraints"
MUST_NOT_OWN = "generic workflow scheduling"
AUTHORITY = "scientific_protocol"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="scientific",
    node="scientific/protocol",
    package_prefix='research_platform.scientific.protocol',
    authority_id="scientific_protocol",
    owns="scientific protocol definitions and execution constraints",
    must_not_own="generic workflow scheduling",
    api_module='research_platform.scientific.protocol.api',
    runtime_module='research_platform.scientific.protocol.runtime',
    provider_module='research_platform.scientific.protocol.providers',
    composition_module='research_platform.scientific.protocol.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
