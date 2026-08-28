from research_platform.data.state.api import AggregateValue
from research_platform.data.state.runtime import SQLiteAtomicStateStore
import tempfile
import unittest
from pathlib import Path

from research_platform.experimentation.evaluation.api import ComparabilityProof
from projects.sem_paper.method.self_evolving_memory.adoption import AtomicAdoptionService
from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore, InMemoryEvidenceSnapshotSource
from projects.sem_paper.method.self_evolving_memory.evolution import CandidateArchitecture, EvaluationProof, PrimitiveEdit, PrimitiveEditKind
from projects.sem_paper.method.self_evolving_memory.generation import GenerationAllocator, PreparedStatus
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract, Materializer


class SEMDurableAdoptionV101Tests(unittest.TestCase):
    def test_adoption_authority_survives_process_level_store_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"sem-state.sqlite3"
            store=SQLiteAtomicStateStore(path,(
                AggregateValue(AtomicAdoptionService.ARCH,1,"g1","a",{"old":1}),
                AggregateValue(AtomicAdoptionService.LEDGER,1,"g1","l",[]),
            ))
            allocator=GenerationAllocator()
            service=AtomicAdoptionService(store,Materializer(InMemoryEvidenceSnapshotSource(InMemoryEvidenceStore())),allocator)
            proof=EvaluationProof(ComparabilityProof(True,"pair",(),"cp","w","env","task"),{})
            candidate=CandidateArchitecture(
                "g1","candidate",{"nodes":["n"]},"spec",
                (PrimitiveEdit(PrimitiveEditKind.CREATE,"n"),),
                (MaterializationContract("n",{},{}),),
            )
            generation=service.adopt(candidate,proof)
            reopened=SQLiteAtomicStateStore(path)
            self.assertEqual(reopened.read(AtomicAdoptionService.ARCH).generation,generation)
            self.assertEqual(reopened.read(AtomicAdoptionService.LEDGER).generation,generation)
            fresh=GenerationAllocator()
            recovered=AtomicAdoptionService(reopened,Materializer(InMemoryEvidenceSnapshotSource(InMemoryEvidenceStore())),fresh)
            self.assertEqual(recovered.reconcile_committed_generation(),generation)
            self.assertEqual(fresh.status(generation),PreparedStatus.COMMITTED)


if __name__ == "__main__":
    unittest.main()
