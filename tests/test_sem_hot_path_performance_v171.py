from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from research_platform.platform.kernel import ExecutionContext

from projects.sem_paper.method.self_evolving_memory.evidence_memory import InMemoryEvidenceStore, build_evidence_record
from projects.sem_paper.method.self_evolving_memory.session_state_memory import InMemorySEMSessionStateFactory
from projects.sem_paper.method.self_evolving_memory.session_serving import ReadOnlyServingSessionSource
from projects.sem_paper.method.self_evolving_memory.retrieval_planner import HybridLexicalRecencyQueryPlanner, LatestEvidenceQueryPlanner
from projects.sem_paper.method.self_evolving_memory.serving import MemoryServingService


class SEMHotPathPerformanceV171Tests(unittest.TestCase):
    def test_incremental_evidence_digest_matches_canonical_chain(self):
        store = InMemoryEvidenceStore()
        signatures = []
        for sequence in range(1, 101):
            row = build_evidence_record(f"e{sequence}", sequence, {"value": sequence})
            store.append(row)
            signatures.append(f"{row.sequence}:{row.evidence_id}:{row.digest}")
            expected = hashlib.sha256("\n".join(signatures).encode()).hexdigest()
            self.assertEqual(store.cut().digest, expected)

    def test_duplicate_detection_does_not_iterate_existing_rows(self):
        store = InMemoryEvidenceStore()
        for sequence in range(1, 1001):
            store.append(build_evidence_record(f"e{sequence}", sequence, sequence))
        with self.assertRaisesRegex(ValueError, "duplicate J_mem evidence_id"):
            store.append(build_evidence_record("e500", 1001, "duplicate"))
        self.assertEqual(store.cut().count, 1000)

    def test_latest_recall_serializes_only_selected_payload(self):
        cell = InMemorySEMSessionStateFactory().create("s")
        context = ExecutionContext("run", "trace", "span")
        for sequence in range(100):
            cell.ingest({"value": sequence}, context)
        service = MemoryServingService(
            ReadOnlyServingSessionSource(cell),
            LatestEvidenceQueryPlanner(),
        )
        from projects.sem_paper.method.self_evolving_memory import session_serving
        original = session_serving.canonical_text
        with patch.object(session_serving, "canonical_text", wraps=original) as encode:
            result = service.recall("latest", limit=8)
        self.assertEqual(result.context_text, '{"value":99}')
        self.assertEqual(encode.call_count, 1)


    def test_hybrid_index_reuses_cached_prefix_and_indexes_only_new_evidence(self):
        cell = InMemorySEMSessionStateFactory().create("s")
        context = ExecutionContext("run", "trace", "span")
        for sequence in range(100):
            cell.ingest({"topic": "pressure", "value": sequence}, context)
        service = MemoryServingService(
            ReadOnlyServingSessionSource(cell),
            HybridLexicalRecencyQueryPlanner(max_nodes=8),
        )
        from projects.sem_paper.method.self_evolving_memory import session_serving
        original = session_serving.canonical_text
        with patch.object(session_serving, "canonical_text", wraps=original) as encode:
            first = service.recall("pressure", limit=2)
            first_calls = encode.call_count
            second = service.recall("pressure", limit=2)
            second_calls = encode.call_count - first_calls
            cell.ingest({"topic": "pressure", "value": 100}, context)
            third = service.recall("pressure", limit=2)
            third_calls = encode.call_count - first_calls - second_calls
        self.assertEqual(first.selected_nodes[-1], second.selected_nodes[-1])
        self.assertGreaterEqual(first_calls, 100)
        self.assertEqual(second_calls, 2)
        self.assertEqual(third_calls, 3)
        self.assertIn('"value":100', third.context_text)

    def test_pinned_lazy_snapshot_does_not_see_later_append(self):
        cell = InMemorySEMSessionStateFactory().create("s")
        context = ExecutionContext("run", "trace", "span")
        cell.ingest({"value": 1}, context)
        snapshot = ReadOnlyServingSessionSource(cell).open_snapshot()
        cell.ingest({"value": 2}, context)
        self.assertEqual(snapshot.node_count, 1)
        self.assertEqual(snapshot.latest_node_id(), "s:jmem:1")
        self.assertEqual(snapshot.resolve(("s:jmem:1",)), (("s:jmem:1", '{"value":1}'),))
        self.assertFalse(snapshot.contains("s:jmem:2"))


if __name__ == "__main__":
    unittest.main()
