# vNext Boundary: reliability/recovery/replay

SYSTEM = "reliability"
NODE = "reliability/recovery/replay"
OWNS = "exact replay contracts against frozen identities"
MUST_NOT_OWN = "new identity selection"
AUTHORITY = "recovery_replay"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/recovery/replay",
    package_prefix='research_platform.reliability.recovery.replay',
    authority_id="recovery_replay",
    owns="exact replay contracts against frozen identities",
    must_not_own="new identity selection",
    api_module='research_platform.reliability.recovery.replay.api',
    runtime_module='research_platform.reliability.recovery.replay.runtime',
    provider_module='research_platform.reliability.recovery.replay.providers',
    composition_module='research_platform.reliability.recovery.replay.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
