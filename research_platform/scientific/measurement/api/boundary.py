# vNext Boundary: scientific/measurement

SYSTEM = "scientific"
NODE = "scientific/measurement"
OWNS = "measurement definitions and scientific result semantics"
MUST_NOT_OWN = "telemetry infrastructure"
AUTHORITY = "measurement_semantics"

# This module is intentionally declarative. Concrete behavior belongs in runtime/providers.


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="scientific",
    node="scientific/measurement",
    package_prefix='research_platform.scientific.measurement',
    authority_id="measurement_semantics",
    owns="measurement definitions and scientific result semantics",
    must_not_own="telemetry infrastructure",
    api_module='research_platform.scientific.measurement.api',
    runtime_module='research_platform.scientific.measurement.runtime',
    provider_module='research_platform.scientific.measurement.providers',
    composition_module='research_platform.scientific.measurement.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
