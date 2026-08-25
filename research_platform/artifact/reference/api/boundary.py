# vNext Boundary: artifact/reference

SYSTEM = "artifact"
NODE = "artifact/reference"
OWNS = "references, aliases and cross-system artifact pointers"
MUST_NOT_OWN = "content mutation"
AUTHORITY = "artifact_reference"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="artifact",
    node="artifact/reference",
    package_prefix='research_platform.artifact.reference',
    authority_id="artifact_reference",
    owns="references, aliases and cross-system artifact pointers",
    must_not_own="content mutation",
    api_module='research_platform.artifact.reference.api',
    runtime_module='research_platform.artifact.reference.runtime',
    provider_module='research_platform.artifact.reference.providers',
    composition_module='research_platform.artifact.reference.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
