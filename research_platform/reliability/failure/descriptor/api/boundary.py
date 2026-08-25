# vNext Boundary: reliability/failure/descriptor

SYSTEM = "reliability"
NODE = "reliability/failure/descriptor"
OWNS = "safe exception and failure descriptors"
MUST_NOT_OWN = "durable failure lifecycle"
AUTHORITY = "failure_descriptor"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/failure/descriptor",
    package_prefix='research_platform.reliability.failure.descriptor',
    authority_id="failure_descriptor",
    owns="safe exception and failure descriptors",
    must_not_own="durable failure lifecycle",
    api_module='research_platform.reliability.failure.descriptor.api',
    runtime_module='research_platform.reliability.failure.descriptor.runtime',
    provider_module='research_platform.reliability.failure.descriptor.providers',
    composition_module='research_platform.reliability.failure.descriptor.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
