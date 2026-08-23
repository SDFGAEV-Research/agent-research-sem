from __future__ import annotations

from research_platform.experimentation.evaluation.api import ComparabilityProof

from projects.sem_paper.method.self_evolving_memory.evolution import (
    CandidateArchitecture,
    EvaluationProof,
)
from projects.sem_paper.method.self_evolving_memory.session_adoption import (
    PreparedCandidateAdoption,
)


def test_prepared_candidate_adoption_binds_exact_evaluated_artifacts() -> None:
    candidate = CandidateArchitecture("g0", "candidate-1", {}, "digest", (), ())
    proof = EvaluationProof(
        ComparabilityProof(True, "pair-1", (), "cut-1", "workload-1", "env-1", "tasks-1"),
        {"utility": 1.0},
    )
    received: list[tuple[CandidateArchitecture, EvaluationProof]] = []

    class Authority:
        def adopt(self, actual_candidate, actual_proof) -> str:
            received.append((actual_candidate, actual_proof))
            return "g1"

    prepared = PreparedCandidateAdoption(Authority(), candidate, proof)

    assert prepared.commit() == "g1"
    assert received == [(candidate, proof)]
