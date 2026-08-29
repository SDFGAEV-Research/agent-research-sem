from __future__ import annotations

from research_platform.experimentation.evaluation.api import ComparabilityProof
from research_platform.data.state.runtime import SQLiteAtomicStateStore
from projects.sem_paper.composition.candidate_method import build_seed_x_candidate
from projects.sem_paper.composition.evolution import SemPaperEvolutionBindings
from projects.sem_paper.composition.evolution_production import (
    DeferredMinecraftPairedEvolutionEvaluator,
    DurableSessionEvolutionAuthority,
)
from projects.sem_paper.method.self_evolving_memory.architecture import (
    SemPaperArchitecturePreset,
    build_sem_paper_architecture,
)
from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore
from projects.sem_paper.method.self_evolving_memory.evolution import EvaluationProof
from projects.sem_paper.method.self_evolving_memory.session_evolution_api import (
    EvolutionReconciliationStatus,
)


class _SessionAuthority:
    def __init__(self) -> None:
        self._generation = "g0"
        self.evidence = InMemoryEvidenceStore()
        self.evidence.append_payload("e1", 1, {"kind": "test"})

    @property
    def session_id(self) -> str:
        return "production-evolution-test"

    def open_evidence_cut(self):
        return self._generation, self.evidence.read_view()

    def commit_prepared_adoption(self, adoption, context):
        del context
        generation = adoption.commit()
        self._generation = generation
        from projects.sem_paper.method.self_evolving_memory.session_evolution_api import (
            SessionAdoptionPublication,
        )
        from projects.sem_paper.method.self_evolving_memory.session_mutation import SessionMutationRecord
        mutation = SessionMutationRecord(
            sequence=1,
            mutation_type="ADOPTION_COMMIT",
            before_digest="b" * 64,
            after_digest="a" * 64,
            evidence_refs=(),
        )
        return SessionAdoptionPublication(generation, mutation)


def test_deferred_evaluator_blocks_until_runtime_is_bound() -> None:
    evaluator = DeferredMinecraftPairedEvolutionEvaluator()
    bindings = SemPaperEvolutionBindings(
        proposal=object(), evaluator=evaluator,
        adoption=object(), reconciliation=object(),
    )
    assert bindings.scientific_ready
    assert not bindings.runtime_ready
    try:
        evaluator.bind_session("session-a")
    except RuntimeError as exc:
        assert "runtime is not bound" in str(exc)
    else:
        raise AssertionError("unbound production evaluator must fail closed")

def test_durable_session_authority_persists_adoption_and_reconciles(tmp_path) -> None:
    session = _SessionAuthority()
    authority = DurableSessionEvolutionAuthority(tmp_path, state_store_factory=SQLiteAtomicStateStore)
    initial = build_sem_paper_architecture(SemPaperArchitecturePreset.C)
    bound = authority.bind(session, initial_architecture=initial)
    candidate = build_seed_x_candidate(base_generation="g0")
    proof = EvaluationProof(
        ComparabilityProof(True, "pair", (), "cp", "work", "env", "tasks"),
        {"delta.utility": 1.0},
    )
    generation = bound.adopt(candidate, proof)
    assert generation != "g0"
    assert bound.current_architecture(generation) == candidate.target_spec
    reconciled = bound.reconcile(
        task_key="task-1",
        base_generation="g0",
        context=None,  # reconciliation does not consume execution context
    )
    assert reconciled.status is EvolutionReconciliationStatus.ADOPTION_CONFIRMED
    assert reconciled.authoritative_generation == generation

    reopened = DurableSessionEvolutionAuthority(
        tmp_path, state_store_factory=SQLiteAtomicStateStore
    ).bind(
        session,
        initial_architecture=initial,
    )
    assert reopened.current_architecture(generation) == candidate.target_spec
    recovered = reopened.reconcile(task_key="task-1", base_generation="g0", context=None)
    assert recovered.status is EvolutionReconciliationStatus.ADOPTION_CONFIRMED
    assert recovered.authoritative_generation == generation
