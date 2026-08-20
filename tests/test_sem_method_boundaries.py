import inspect, unittest
from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore, InMemoryEvidenceSnapshotSource, build_evidence_record
from projects.sem_paper.method.self_evolving_memory.evidence_api import EvidenceSnapshotPort
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract, Materializer
from projects.sem_paper.method.self_evolving_memory.serving import MemoryServingService
from projects.sem_paper.method.self_evolving_memory.evolution import *
from projects.sem_paper.method.self_evolving_memory.authority import validate_tier_authority
from research_platform.experimentation.evaluation.api import ComparabilityProof

class StaticSnapshot:
    generation="g1"
    node_count=1
    def latest_node_id(self): return "n1"
    def contains(self,node_id): return node_id=="n1"
    def node_ids(self): return ("n1",)
    def node_features(self,node_id): return frozenset({"x"}) if node_id=="n1" else frozenset()
    def candidate_node_ids(self,query_features): return ("n1",) if "x" in query_features else ()
    def node_sequence(self,node_id): return 1 if node_id=="n1" else None
    def resolve(self,node_ids): return tuple((node_id,"ctx") for node_id in node_ids if node_id=="n1")

class Snap:
    def open_snapshot(self): return StaticSnapshot()
class Plan:
    def plan(self,intent,snapshot,*,limit): return ("n1",)
class D:
    def diagnose(self): return ArchitectureObservationReport("g1","neutral",())
class S:
    def __init__(self): self.calls=0
    def propose(self,a): self.calls+=1; return StructuralIntent(EditKind.CREATE,"r",{})
class C:
    def compile(self,i,b): return CandidateArchitecture(b,"c",{},"digest",(PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),(MaterializationContract("n",{},{}),))
class E:
    def evaluate(self,c): return EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","e","t"),{"gain":1})
class A:
    def accept(self,i,p): return True
class Adopt:
    def __init__(self): self.calls=0
    def adopt(self,c,p): self.calls+=1; return "g2"

class SEMBoundaries(unittest.TestCase):
    def test_materializer_cannot_receive_audit_store_by_type_contract(self):
        self.assertEqual(inspect.signature(Materializer).parameters["evidence"].annotation,"EvidenceSnapshotPort")
        mem=InMemoryEvidenceStore(); mem.append(build_evidence_record("e",1,{}))
        p=Materializer(InMemoryEvidenceSnapshotSource(mem)).clean_build("g2",base_generation="g1",candidate_id="c",target_spec_digest="d",contracts=(MaterializationContract("n",{},{}),))
        self.assertEqual(p.source_sequence,1)
    def test_serving_is_generation_pinned(self):
        r=MemoryServingService(Snap(),Plan()).recall("x",limit=1); self.assertEqual((r.generation,r.context_text),("g1","ctx"))
    def test_synthesis_has_no_adopt_method(self): self.assertFalse(hasattr(S(),"adopt"))
    def test_pipeline_adopts_only_after_valid_proof_and_policy(self):
        ad=Adopt(); out=EvolutionPipeline(eligibility=type("G",(),{"check":lambda self: EvolutionEligibility(True,"eligible")})(),diagnosis=D(),synthesis=S(),compiler=C(),evaluator=E(),acceptance=A(),adoption=ad).run(); self.assertEqual(out.final_generation,"g2"); self.assertEqual(ad.calls,1)

    def test_pipeline_failure_is_attributed_to_exact_stage_without_raw_cause_text(self):
        class BadDiagnosis:
            def diagnose(self): raise RuntimeError("secret-stage-detail")
        pipeline=EvolutionPipeline(
            eligibility=type("G",(),{"check":lambda self: EvolutionEligibility(True,"eligible")})(),
            diagnosis=BadDiagnosis(), synthesis=S(), compiler=C(), evaluator=E(), acceptance=A(), adoption=Adopt(),
        )
        with self.assertRaises(EvolutionStageFailure) as cm:
            pipeline.run()
        self.assertEqual(cm.exception.stage, EvolutionStage.DIAGNOSIS)
        self.assertNotIn("secret-stage-detail", str(cm.exception))
        self.assertEqual(cm.exception.failure_correlation_refs, ("evolution-stage:diagnosis",))

    def test_tier_authority_equal(self): validate_tier_authority()
if __name__=="__main__": unittest.main()
