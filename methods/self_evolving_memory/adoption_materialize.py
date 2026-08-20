from __future__ import annotations

from .adoption_types import AdoptionPreparationError, AdoptionPreparationStage, MaterializedCandidate
from .evolution import CandidateArchitecture
from .generation import GenerationAllocator
from .materialization import Materializer


class PreparedGenerationBuilder:
    """Owns allocate -> clean materialize -> abandon-on-failure lifecycle."""

    def __init__(self, materializer: Materializer, allocator: GenerationAllocator) -> None:
        self.materializer = materializer
        self.allocator = allocator

    def build(self, candidate: CandidateArchitecture) -> MaterializedCandidate:
        try:
            generation = self.allocator.allocate(candidate.candidate_id)
        except Exception as exc:
            raise AdoptionPreparationError(
                AdoptionPreparationStage.GENERATION,
                "ADOPTION_GENERATION_ALLOCATE_FAILED",
                str(exc),
            ) from exc
        try:
            prepared = self.materializer.clean_build(
                generation,
                base_generation=candidate.base_generation,
                candidate_id=candidate.candidate_id,
                target_spec_digest=candidate.target_spec_digest,
                contracts=tuple(candidate.materialization_contracts),
            )
        except Exception as exc:
            self.allocator.abandon(generation)
            raise AdoptionPreparationError(
                AdoptionPreparationStage.MATERIALIZATION,
                "ADOPTION_MATERIALIZATION_FAILED",
                str(exc),
            ) from exc
        return MaterializedCandidate(generation, prepared)

    def abandon(self, generation: str) -> None:
        self.allocator.abandon(generation)
