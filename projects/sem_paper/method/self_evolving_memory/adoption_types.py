from __future__ import annotations

from research_platform.data.state.api import AtomicMutation

from dataclasses import dataclass
from enum import StrEnum

from .materialization import PreparedGeneration


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


@dataclass(frozen=True, slots=True)
class PreparedAdoption:
    generation: str
    prepared_generation: PreparedGeneration
    architecture_mutation: AtomicMutation
    ledger_mutation: AtomicMutation
    ledger_entry: EvolutionLedgerEntry


@dataclass(frozen=True, slots=True)
class AdoptionBaseState:
    architecture: object
    ledger: object


@dataclass(frozen=True, slots=True)
class MaterializedCandidate:
    generation: str
    prepared_generation: PreparedGeneration
