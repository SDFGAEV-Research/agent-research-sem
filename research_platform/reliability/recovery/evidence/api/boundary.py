# vNext Boundary: reliability/recovery/evidence

SYSTEM = "reliability"
NODE = "reliability/recovery/evidence"
OWNS = "recovery evidence receipts and proof of reconciliation"
MUST_NOT_OWN = "diagnostic projections"
AUTHORITY = "recovery_evidence"


from research_platform.platform.kernel.leaf_contract import SystemLeafContract


CONTRACT = SystemLeafContract(
    system_id="reliability",
    node="reliability/recovery/evidence",
    package_prefix='research_platform.reliability.recovery.evidence',
    authority_id="recovery_evidence",
    owns="recovery evidence receipts and proof of reconciliation",
    must_not_own="diagnostic projections",
    api_module='research_platform.reliability.recovery.evidence.api',
    runtime_module='research_platform.reliability.recovery.evidence.runtime',
    provider_module='research_platform.reliability.recovery.evidence.providers',
    composition_module='research_platform.reliability.recovery.evidence.composition',
)


def contract() -> SystemLeafContract:
    return CONTRACT
