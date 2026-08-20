from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BranchReceipt:
    branch_id: str
    source_checkpoint_id: str
    workload_id: str
    environment_generation: str
    task_manifest_digest: str
    branch_writes: tuple[str, ...]
    lifetime_writes: tuple[str, ...]
    private_to_method_flows: tuple[str, ...]
    metrics: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class ComparabilityProof:
    valid: bool
    pair_id: str
    violations: tuple[str, ...]
    source_checkpoint_id: str
    workload_id: str
    environment_generation: str
    task_manifest_digest: str


@dataclass(frozen=True, slots=True)
class PairedEvaluationResult:
    control: BranchReceipt
    candidate: BranchReceipt
    proof: ComparabilityProof


__all__ = ["BranchReceipt", "ComparabilityProof", "PairedEvaluationResult"]
