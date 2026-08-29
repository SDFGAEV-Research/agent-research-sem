from research_platform.data.state.api import AggregateValue, AtomicMutation, StateVersionConflict
from research_platform.data.state.runtime import InMemoryAtomicStateStore
import unittest
from unittest import mock

from projects.sem_paper.method.self_evolving_memory.adoption import AtomicAdoptionService, GenerationAllocator
from projects.sem_paper.method.self_evolving_memory.adoption_commit import AdoptionCommitConsistencyError
from projects.sem_paper.method.self_evolving_memory.generation import GenerationLifecycleConflict
from projects.sem_paper.method.self_evolving_memory.adoption_preparation import (
    AdoptionPreparationError, AdoptionPreparationStage, AdoptionMutationCompiler,
)
from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore, InMemoryEvidenceSnapshotSource, build_evidence_record
from projects.sem_paper.method.self_evolving_memory.evolution import (
    ArchitectureObservationReport, CandidateArchitecture, EditKind, EvaluationProof, EvolutionEligibility,
    EvolutionPipeline, OperationalVerifier, PrimitiveEdit, PrimitiveEditKind, StructuralCompiler, StructuralIntent,
)
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract, Materializer, PreparedStatus
from research_platform.experimentation.evaluation.api import BranchReceipt, ComparabilityProof
from research_platform.experimentation.evaluation.runtime import build_comparability_proof


def receipt(branch, **kw):
    base=dict(source_checkpoint_id="cp",workload_id="w",environment_generation="env",task_manifest_digest="task",branch_writes=(),lifetime_writes=(),private_to_method_flows=(),metrics=(("score",1.0),))
    base.update(kw); return BranchReceipt(branch,**base)

class SEMV14Tests(unittest.TestCase):
    def test_private_evaluation_flow_invalidates_comparability(self):
        p=build_comparability_proof(receipt("control"),receipt("candidate",private_to_method_flows=("j_eval->method",)))
        self.assertFalse(p.valid); self.assertIn("private evaluation/control evidence flowed into method state",p.violations)

    def test_split_and_merge_compile_to_create_retire_only(self):
        def target(base,edits,intent): return ({"base":base,"edits":[e.kind.value for e in edits]},(MaterializationContract("whole",{},{}),))
        c=StructuralCompiler(target)
        split=c.compile(StructuralIntent(EditKind.SPLIT,"r",{"parent":"p","children":["a","b"]}),"g1")
        self.assertEqual([e.kind for e in split.primitive_edits],[PrimitiveEditKind.CREATE,PrimitiveEditKind.CREATE,PrimitiveEditKind.RETIRE])
        merge=c.compile(StructuralIntent(EditKind.MERGE,"r",{"sources":["a","b"],"target":"m"}),"g1")
        self.assertEqual([e.kind for e in merge.primitive_edits],[PrimitiveEditKind.CREATE,PrimitiveEditKind.RETIRE,PrimitiveEditKind.RETIRE])
        OperationalVerifier().verify(split)
        self.assertFalse(hasattr(OperationalVerifier(),"accept"))

    def test_atomic_store_conflict_is_zero_write(self):
        s=InMemoryAtomicStateStore((AggregateValue("a",1,"g1","d",1),AggregateValue("b",2,"g1","e",2)))
        with self.assertRaises(StateVersionConflict): s.commit_batch((AtomicMutation("a",1,"g1","g2","x",3),AtomicMutation("b",999,"g1","g2","y",4)))
        self.assertEqual((s.read("a").version,s.read("b").version),(1,2))

    def _adoption(self):
        mem=InMemoryEvidenceStore(); mem.append(build_evidence_record("e1",1,{"x":1})); materializer=Materializer(InMemoryEvidenceSnapshotSource(mem)); allocator=GenerationAllocator()
        state=InMemoryAtomicStateStore((AggregateValue(AtomicAdoptionService.ARCH,1,"g1","a",{"old":1}),AggregateValue(AtomicAdoptionService.LEDGER,1,"g1","l",())))
        return state,allocator,AtomicAdoptionService(state,materializer,allocator)

    def test_adoption_clean_builds_and_atomically_moves_head_and_ledger(self):
        state,allocator,adopt=self._adoption(); proof=EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","env","task"),{"gain":1})
        c=CandidateArchitecture("g1","candidate",{"nodes":["n"]},"spec",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",{},{}),))
        g=adopt.adopt(c,proof)
        self.assertEqual(state.read(AtomicAdoptionService.ARCH).generation,g); self.assertEqual(state.read(AtomicAdoptionService.LEDGER).generation,g); self.assertEqual(allocator.status(g),PreparedStatus.COMMITTED)
        self.assertEqual(state.read(AtomicAdoptionService.ARCH).payload["source_sequence"],1)

    def test_stale_candidate_never_allocates_generation(self):
        state,allocator,adopt=self._adoption(); proof=EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","env","task"),{})
        c=CandidateArchitecture("old","candidate",{},"spec",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",{},{}),))
        with self.assertRaises(AdoptionPreparationError) as cm: adopt.adopt(c,proof)
        self.assertEqual(cm.exception.stage, AdoptionPreparationStage.BASE_STATE)
        self.assertEqual(cm.exception.code, "ADOPTION_BASE_STALE")
        self.assertEqual(allocator.snapshot(),{})

    def test_commit_failure_abandons_prepared_generation(self):
        state,allocator,adopt=self._adoption(); proof=EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","env","task"),{})
        c=CandidateArchitecture("g1","candidate",{},"spec",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",{},{}),))
        with mock.patch.object(state,"commit_batch",side_effect=OSError("disk")):
            with self.assertRaises(OSError): adopt.adopt(c,proof)
        g=next(iter(allocator.snapshot())); self.assertEqual(allocator.status(g),PreparedStatus.ABANDONED); self.assertEqual(state.read(AtomicAdoptionService.ARCH).generation,"g1")

    def test_materialization_failure_abandons_allocated_generation(self):
        state,allocator,adopt=self._adoption(); proof=EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","env","task"),{})
        c=CandidateArchitecture("g1","candidate",{},"spec",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",object(),{}),))
        with self.assertRaises(AdoptionPreparationError) as cm: adopt.adopt(c,proof)
        self.assertEqual(cm.exception.stage, AdoptionPreparationStage.MATERIALIZATION)
        self.assertEqual(cm.exception.code, "ADOPTION_MATERIALIZATION_FAILED")
        g=next(iter(allocator.snapshot())); self.assertEqual(allocator.status(g),PreparedStatus.ABANDONED)
        self.assertEqual(state.read(AtomicAdoptionService.ARCH).generation,"g1")

    def test_candidate_target_spec_rejects_noncanonical_object(self):
        def target(base,edits,intent): return ({"bad":object()},(MaterializationContract("n",{},{}),))
        with self.assertRaises(TypeError): StructuralCompiler(target).compile(StructuralIntent(EditKind.CREATE,"r",{"node_id":"n"}),"g1")

    def test_deferred_is_not_no_edit_and_synthesis_not_called(self):
        class Gate:
            def check(self): return EvolutionEligibility(False,"minimum_dwell")
        class D:
            def diagnose(self): raise AssertionError("diagnosis must not run")
        out=EvolutionPipeline(eligibility=Gate(),diagnosis=D(),synthesis=None,compiler=None,evaluator=None,acceptance=None,adoption=None).run()
        self.assertEqual(out.status,"deferred"); self.assertIsNone(out.edit); self.assertEqual(out.reason_code,"minimum_dwell")

    def test_invalid_proof_fails_before_generation_allocation(self):
        state,allocator,adopt=self._adoption()
        proof=EvaluationProof(ComparabilityProof(False,"pair",("bad",),"cp","w","env","task"),{})
        c=CandidateArchitecture("g1","candidate",{},"spec",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",{},{}),))
        with self.assertRaises(AdoptionPreparationError) as cm:
            adopt.adopt(c,proof)
        self.assertEqual(cm.exception.stage, AdoptionPreparationStage.PROOF)
        self.assertEqual(allocator.snapshot(),{})

    def test_mutation_compile_failure_abandons_materialized_generation(self):
        state,allocator,adopt=self._adoption()
        proof=EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","env","task"),{})
        c=CandidateArchitecture("g1","candidate",{},"spec",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",{},{}),))
        with mock.patch.object(adopt.preparer.compiler,"compile",side_effect=AdoptionPreparationError(AdoptionPreparationStage.MUTATION_COMPILE,"X","compile")):
            with self.assertRaises(AdoptionPreparationError): adopt.adopt(c,proof)
        g=next(iter(allocator.snapshot()))
        self.assertEqual(allocator.status(g),PreparedStatus.ABANDONED)
        self.assertEqual(state.read(AtomicAdoptionService.ARCH).generation,"g1")

    def test_fresh_allocator_reconciles_committed_generation_from_authoritative_state(self):
        state,allocator,adopt=self._adoption(); proof=EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","env","task"),{})
        c=CandidateArchitecture("g1","candidate",{},"spec",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",{},{}),))
        g=adopt.adopt(c,proof)
        fresh=GenerationAllocator()
        recovered=AtomicAdoptionService(state,Materializer(InMemoryEvidenceSnapshotSource(InMemoryEvidenceStore())),fresh)
        self.assertEqual(recovered.reconcile_committed_generation(),g)
        self.assertEqual(fresh.status(g),PreparedStatus.COMMITTED)

    def test_reconcile_refuses_architecture_ledger_generation_mismatch(self):
        state,allocator,adopt=self._adoption()
        state._values[AtomicAdoptionService.LEDGER]=AggregateValue(AtomicAdoptionService.LEDGER,2,"other","x",())
        with self.assertRaises(AdoptionCommitConsistencyError):
            adopt.reconcile_committed_generation()

    def test_authoritative_commit_cannot_silently_override_abandoned_allocator(self):
        state,allocator,adopt=self._adoption(); proof=EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","env","task"),{})
        c=CandidateArchitecture("g1","candidate",{},"spec",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",{},{}),))
        g=adopt.adopt(c,proof)
        conflicting=GenerationAllocator(); conflicting._status[g]=PreparedStatus.ABANDONED
        recovered=AtomicAdoptionService(state,Materializer(InMemoryEvidenceSnapshotSource(InMemoryEvidenceStore())),conflicting)
        with self.assertRaises(GenerationLifecycleConflict):
            recovered.reconcile_committed_generation()

if __name__=='__main__': unittest.main()
