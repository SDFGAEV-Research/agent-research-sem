from research_platform.participant.method.runtime import InMemoryMethodObservationSink
from tests_support import build_self_evolving_memory_method
import unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodServices, RecallRequest
from projects.sem_paper.method.self_evolving_memory.evolution import EditKind, EvolutionOutcome


class SEMEvolutionIntegrationV100Tests(unittest.TestCase):
    def test_adoption_outcome_syncs_session_generation_without_granting_cell_to_evolution(self):
        seen = []
        class Controller:
            def __init__(self, source): self.source=source
            def on_task_completed(self, context):
                snap=self.source.snapshot(); seen.append(snap)
                return EvolutionOutcome("adopted",snap.generation,"g1",EditKind.CREATE)
        class Factory:
            def __call__(self, source):
                self.source_type=type(source).__name__
                self.has_ingest=hasattr(source,"ingest")
                return Controller(source)
        factory=Factory()
        sink=InMemoryMethodObservationSink()
        method=build_self_evolving_memory_method(evolution_factory=factory,evolution_provider_id="test.evolution.adopt.v1")
        session=method.open_session(session_id="s",services=MethodServices(sink))
        ctx=ExecutionContext("run","trace","span")
        session.ingest({"x":1},ctx)
        session.task_completed({},ctx)
        self.assertFalse(factory.has_ingest)
        self.assertEqual(session.diagnostics()["generation"],"g1")
        self.assertEqual(session.diagnostics()["evolution_epoch"],1)
        self.assertEqual([x.mutation_type for x in session.mutation_history()], ["INGEST","TASK_COMPLETED","ADOPTION_SYNC"])
        self.assertEqual(session.recall(RecallRequest("x",ctx)).method_generation,"g1")
        self.assertEqual(seen[0].tasks_completed,1)
        self.assertEqual([r.payload["mutation_type"] for r in sink.rows()], ["INGEST","TASK_COMPLETED","ADOPTION_SYNC"])

    def test_non_adopted_outcome_cannot_change_generation(self):
        class Controller:
            def on_task_completed(self, context):
                return EvolutionOutcome("rejected","g0","g0",EditKind.CREATE)
        class Factory:
            def __call__(self, source): return Controller()
        session=build_self_evolving_memory_method(evolution_factory=Factory(),evolution_provider_id="test.evolution.reject.v1").open_session(
            session_id="s",services=MethodServices(InMemoryMethodObservationSink())
        )
        ctx=ExecutionContext("run","trace","span")
        session.task_completed({},ctx)
        self.assertEqual(session.diagnostics()["generation"],"g0")
        self.assertEqual(session.diagnostics()["evolution_epoch"],0)


if __name__ == "__main__":
    unittest.main()
