from __future__ import annotations

import hashlib
import json

from research_platform.experimentation.evaluation.api import BranchReceipt, ComparabilityProof


def build_comparability_proof(control: BranchReceipt, candidate: BranchReceipt) -> ComparabilityProof:
    violations: list[str] = []
    fields = (
        ("source_checkpoint_id", control.source_checkpoint_id, candidate.source_checkpoint_id),
        ("workload_id", control.workload_id, candidate.workload_id),
        ("environment_generation", control.environment_generation, candidate.environment_generation),
        ("task_manifest_digest", control.task_manifest_digest, candidate.task_manifest_digest),
    )
    for name, left, right in fields:
        if left != right:
            violations.append(f"{name} mismatch")
    if control.lifetime_writes:
        violations.append("control branch wrote lifetime state")
    if candidate.lifetime_writes:
        violations.append("candidate branch wrote lifetime state")
    if any(item.startswith("candidate->control") for item in candidate.branch_writes):
        violations.append("candidate wrote control branch state")
    if control.private_to_method_flows or candidate.private_to_method_flows:
        violations.append("private evaluation/control evidence flowed into method state")
    raw = json.dumps(
        {
            "c": control.branch_id,
            "x": candidate.branch_id,
            "cp": control.source_checkpoint_id,
            "w": control.workload_id,
            "e": control.environment_generation,
            "t": control.task_manifest_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    pair_id = "pair_" + hashlib.sha256(raw).hexdigest()[:20]
    return ComparabilityProof(
        not violations,
        pair_id,
        tuple(violations),
        control.source_checkpoint_id,
        control.workload_id,
        control.environment_generation,
        control.task_manifest_digest,
    )


__all__ = ["build_comparability_proof"]
