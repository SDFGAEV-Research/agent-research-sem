from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.platform.kernel import canonical_digest
from .evidence_api import EvidenceSnapshotPort


@dataclass(frozen=True, slots=True)
class MaterializationContract:
    node_id: str
    source_selector: object
    transform_plan: object


class PreparedStatus(StrEnum):
    PREPARED = "prepared"
    COMMITTED = "committed"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class PreparedGeneration:
    generation: str
    base_generation: str
    candidate_id: str
    source_sequence: int
    source_snapshot_digest: str
    target_spec_digest: str
    records: tuple[tuple[str, str], ...]
    status: PreparedStatus = PreparedStatus.PREPARED


class Materializer:
    """Clean-generation builder consuming only the canonical J_mem snapshot contract."""

    def __init__(self, evidence: EvidenceSnapshotPort) -> None:
        self.evidence = evidence

    def clean_build(
        self,
        generation: str,
        *,
        base_generation: str,
        candidate_id: str,
        target_spec_digest: str,
        contracts: tuple[MaterializationContract, ...],
    ) -> PreparedGeneration:
        if len({contract.node_id for contract in contracts}) != len(contracts):
            raise ValueError("duplicate node materialization contract")
        cut = self.evidence.snapshot()
        records = tuple(
            (
                contract.node_id,
                f"materialized:{cut.sequence}:"
                f"{canonical_digest({'selector': contract.source_selector, 'transform': contract.transform_plan})[:16]}",
            )
            for contract in contracts
        )
        return PreparedGeneration(
            generation,
            base_generation,
            candidate_id,
            cut.sequence,
            cut.digest,
            target_spec_digest,
            records,
        )
