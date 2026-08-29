from __future__ import annotations

from research_platform.data.state.api import AggregateValue, AtomicMutation

from dataclasses import dataclass
from enum import StrEnum

from .materialization import PreparedGeneration


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


class AdoptionPreparationStage(StrEnum):
    PROOF = "proof"
    BASE_STATE = "base_state"
    GENERATION = "generation"
    MATERIALIZATION = "materialization"
    MUTATION_COMPILE = "mutation_compile"


class AdoptionPreparationError(RuntimeError):
    def __init__(self, stage: AdoptionPreparationStage, code: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code


@dataclass(frozen=True, slots=True)
class EvolutionLedgerEntry:
    candidate_id: str
    base_generation: str
    adopted_generation: str
    evaluation_pair_id: str
    target_spec_digest: str
    source_snapshot_digest: str
    source_sequence: int

    def __post_init__(self) -> None:
        for label, value in (
            ("candidate_id", self.candidate_id),
            ("base_generation", self.base_generation),
            ("adopted_generation", self.adopted_generation),
            ("evaluation_pair_id", self.evaluation_pair_id),
            ("target_spec_digest", self.target_spec_digest),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"evolution ledger {label} must be a non-empty string")
        if not _is_sha256(self.source_snapshot_digest):
            raise ValueError("evolution ledger source snapshot digest must be a lower-case SHA-256 digest")
        if isinstance(self.source_sequence, bool) or not isinstance(self.source_sequence, int) or self.source_sequence < 0:
            raise ValueError("evolution ledger source_sequence must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class PreparedAdoption:
    generation: str
    prepared_generation: PreparedGeneration
    architecture_mutation: AtomicMutation
    ledger_mutation: AtomicMutation
    ledger_entry: EvolutionLedgerEntry

    def __post_init__(self) -> None:
        if not isinstance(self.generation, str) or not self.generation.strip():
            raise ValueError("prepared adoption generation must be a non-empty string")
        if not isinstance(self.prepared_generation, PreparedGeneration):
            raise ValueError("prepared adoption materialization is invalid")
        if not isinstance(self.architecture_mutation, AtomicMutation) or not isinstance(self.ledger_mutation, AtomicMutation):
            raise ValueError("prepared adoption mutations must be AtomicMutation values")
        if not isinstance(self.ledger_entry, EvolutionLedgerEntry):
            raise ValueError("prepared adoption ledger entry is invalid")
        if any(value != self.generation for value in (
            self.prepared_generation.generation,
            self.architecture_mutation.new_generation,
            self.ledger_mutation.new_generation,
            self.ledger_entry.adopted_generation,
        )):
            raise ValueError("prepared adoption generation identities do not match")
        if self.ledger_entry.candidate_id != self.prepared_generation.candidate_id:
            raise ValueError("prepared adoption candidate identity does not match ledger entry")
        if self.ledger_entry.base_generation != self.prepared_generation.base_generation:
            raise ValueError("prepared adoption base generation does not match ledger entry")
        if self.ledger_entry.target_spec_digest != self.prepared_generation.target_spec_digest:
            raise ValueError("prepared adoption target spec digest does not match ledger entry")
        if (
            self.ledger_entry.source_sequence != self.prepared_generation.source_sequence
            or self.ledger_entry.source_snapshot_digest != self.prepared_generation.source_snapshot_digest
        ):
            raise ValueError("prepared adoption source cut does not match ledger entry")


@dataclass(frozen=True, slots=True)
class AdoptionBaseState:
    architecture: AggregateValue
    ledger: AggregateValue

    def __post_init__(self) -> None:
        if not isinstance(self.architecture, AggregateValue) or not isinstance(self.ledger, AggregateValue):
            raise ValueError("adoption base state requires typed aggregate values")


@dataclass(frozen=True, slots=True)
class MaterializedCandidate:
    generation: str
    prepared_generation: PreparedGeneration

    def __post_init__(self) -> None:
        if not isinstance(self.generation, str) or not self.generation.strip():
            raise ValueError("materialized candidate generation must be a non-empty string")
        if not isinstance(self.prepared_generation, PreparedGeneration):
            raise ValueError("materialized candidate prepared generation is invalid")
        if self.prepared_generation.generation != self.generation:
            raise ValueError("materialized candidate generation identity mismatch")
