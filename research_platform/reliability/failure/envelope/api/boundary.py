# vNext Boundary: reliability/failure/envelope

SYSTEM = "reliability"
NODE = "reliability/failure/envelope"
OWNS = "durable failure envelopes and lifecycle references"
MUST_NOT_OWN = "incident grouping"
AUTHORITY = "failure_envelope"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/failure/envelope",
    package_prefix='research_platform.reliability.failure.envelope',
    authority_id="failure_envelope",
    owns="durable failure envelopes and lifecycle references",
    must_not_own="incident grouping",
    api_module='research_platform.reliability.failure.envelope.api',
    runtime_module='research_platform.reliability.failure.envelope.runtime',
    provider_module='research_platform.reliability.failure.envelope.providers',
    composition_module='research_platform.reliability.failure.envelope.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
