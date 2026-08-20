from tests_support import build_fixed_memory_method, build_self_evolving_memory_method
from research_platform.participant.method.runtime import InMemoryMethodObservationSink
from tests_support import build_fixed_memory_method
import unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodServices, RecallRequest
from projects.sem_paper.method.self_evolving_memory.session_state_memory import InMemorySEMSessionStateFactory
from projects.sem_paper.method.self_evolving_memory.session_serving import ReadOnlyServingSessionSource


class SEMServingIntegrationV99Tests(unittest.TestCase):
    def test_session_recall_uses_pinned_serving_snapshot_without_behavior_drift(self):
        services = MethodServices(InMemoryMethodObservationSink())
        session = build_fixed_memory_method().open_session(session_id="s", services=services)
        ctx = ExecutionContext("run", "trace", "span")
        session.ingest({"x": 1}, ctx)
        session.ingest({"x": 2}, ctx)
        result = session.recall(RecallRequest("anything", ctx))
        self.assertEqual(result.context_text, '{"x":2}')
        self.assertEqual(result.method_generation, "g0")

    def test_snapshot_adapter_is_read_only_and_generation_pinned(self):
        cell = InMemorySEMSessionStateFactory().create("s")
        ctx = ExecutionContext("run", "trace", "span")
        cell.ingest({"x": 1}, ctx)
        before = cell.diagnostics()["revision"]
        snap = ReadOnlyServingSessionSource(cell).open_snapshot()
        after = cell.diagnostics()["revision"]
        self.assertEqual(before, after)
        self.assertEqual(snap.generation, "g0")
        self.assertEqual(snap.node_count, 1)
        self.assertEqual(snap.node_ids(), ("s:jmem:1",))


if __name__ == "__main__":
    unittest.main()
