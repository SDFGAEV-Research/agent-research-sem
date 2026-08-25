# vNext Boundary: artifact/retention

SYSTEM = "artifact"
NODE = "artifact/retention"
OWNS = "retention, pinning and garbage-collection policy"
MUST_NOT_OWN = "business state semantics"
AUTHORITY = "artifact_retention"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="artifact",
    node="artifact/retention",
    package_prefix='research_platform.artifact.retention',
    authority_id="artifact_retention",
    owns="retention, pinning and garbage-collection policy",
    must_not_own="business state semantics",
    api_module='research_platform.artifact.retention.api',
    runtime_module='research_platform.artifact.retention.runtime',
    provider_module='research_platform.artifact.retention.providers',
    composition_module='research_platform.artifact.retention.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
