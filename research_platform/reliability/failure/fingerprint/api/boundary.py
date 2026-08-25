# vNext Boundary: reliability/failure/fingerprint

SYSTEM = "reliability"
NODE = "reliability/failure/fingerprint"
OWNS = "exact and family failure fingerprints"
MUST_NOT_OWN = "failure severity policy"
AUTHORITY = "failure_fingerprint"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/failure/fingerprint",
    package_prefix='research_platform.reliability.failure.fingerprint',
    authority_id="failure_fingerprint",
    owns="exact and family failure fingerprints",
    must_not_own="failure severity policy",
    api_module='research_platform.reliability.failure.fingerprint.api',
    runtime_module='research_platform.reliability.failure.fingerprint.runtime',
    provider_module='research_platform.reliability.failure.fingerprint.providers',
    composition_module='research_platform.reliability.failure.fingerprint.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
