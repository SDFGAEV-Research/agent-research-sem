from __future__ import annotations

from research_platform.data.state.api import AtomicMutation

from .adoption_types import (
    AdoptionBaseState,
    AdoptionPreparationError,
    AdoptionPreparationStage,
    EvolutionLedgerEntry,
    MaterializedCandidate,
    PreparedAdoption,
)
from research_platform.platform.kernel import canonical_digest
from .evolution import CandidateArchitecture, EvaluationProof


class AdoptionMutationCompiler:
    """Compiles prepared method data into the two authoritative atomic mutations."""

    def __init__(self, *, architecture_aggregate: str, ledger_aggregate: str) -> None:
        self.architecture_aggregate = architecture_aggregate
        self.ledger_aggregate = ledger_aggregate

    @staticmethod
    def _ledger_document(entries: tuple[object, ...]) -> list[dict[str, object]]:
        rows=[]
        for x in entries:
            if isinstance(x, EvolutionLedgerEntry):
                rows.append({
                    "candidate_id": x.candidate_id,
                    "base_generation": x.base_generation,
                    "adopted_generation": x.adopted_generation,
                    "evaluation_pair_id": x.evaluation_pair_id,
                    "target_spec_digest": x.target_spec_digest,
                    "source_snapshot_digest": x.source_snapshot_digest,
                    "source_sequence": x.source_sequence,
                })
            elif isinstance(x, dict):
                rows.append(dict(x))
            else:
                raise TypeError(f"unsupported evolution ledger payload row: {type(x).__name__}")
        return rows

    def compile(self, candidate: CandidateArchitecture, proof: EvaluationProof, base: AdoptionBaseState, materialized: MaterializedCandidate) -> PreparedAdoption:
        prepared = materialized.prepared_generation
        generation = materialized.generation
        try:
            entry = EvolutionLedgerEntry(
                candidate.candidate_id,
                candidate.base_generation,
                generation,
                proof.comparability.pair_id,
                candidate.target_spec_digest,
                prepared.source_snapshot_digest,
                prepared.source_sequence,
            )
            arch_payload = {
                "target_spec": candidate.target_spec,
                "materialized_records": prepared.records,
                "source_sequence": prepared.source_sequence,
                "source_snapshot_digest": prepared.source_snapshot_digest,
            }
            ledger_entries = tuple(base.ledger.payload) + (entry,)
            ledger_payload = self._ledger_document(ledger_entries)
            return PreparedAdoption(
                generation=generation,
                prepared_generation=prepared,
                architecture_mutation=AtomicMutation(
                    self.architecture_aggregate,
                    base.architecture.version,
                    base.architecture.generation,
                    generation,
                    canonical_digest(arch_payload),
                    arch_payload,
                ),
                ledger_mutation=AtomicMutation(
                    self.ledger_aggregate,
                    base.ledger.version,
                    base.ledger.generation,
                    generation,
                    canonical_digest(ledger_payload),
                    ledger_payload,
                ),
                ledger_entry=entry,
            )
        except Exception as exc:
            raise AdoptionPreparationError(
                AdoptionPreparationStage.MUTATION_COMPILE,
                "ADOPTION_MUTATION_COMPILE_FAILED",
                str(exc),
            ) from exc
