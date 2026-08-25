# vNext Boundary: observability/logging/capture

SYSTEM = "observability"
NODE = "observability/logging/capture"
OWNS = "raw process/stream/event capture before semantic logging"
MUST_NOT_OWN = "semantic event taxonomy"
AUTHORITY = "raw_capture"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="observability",
    node="observability/logging/capture",
    package_prefix='research_platform.observability.logging.capture',
    authority_id="raw_capture",
    owns="raw process/stream/event capture before semantic logging",
    must_not_own="semantic event taxonomy",
    api_module='research_platform.observability.logging.capture.api',
    runtime_module='research_platform.observability.logging.capture.runtime',
    provider_module='research_platform.observability.logging.capture.providers',
    composition_module='research_platform.observability.logging.capture.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
