from __future__ import annotations

from dataclasses import dataclass

from .evolution import AdoptionPort, CandidateArchitecture, EvaluationProof


@dataclass(frozen=True, slots=True)
class PreparedCandidateAdoption:
    """Bind evaluated artifacts into the session's minimal commit capability."""

    authority: AdoptionPort
    candidate: CandidateArchitecture
    proof: EvaluationProof

    def commit(self) -> str:
        return self.authority.adopt(self.candidate, self.proof)


__all__ = ["PreparedCandidateAdoption"]
