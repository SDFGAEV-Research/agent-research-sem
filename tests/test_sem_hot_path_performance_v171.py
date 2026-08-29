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
from projects.sem_paper.method.self_evolving_memory.evolution import (
    QueryRecordObservation,
    TaskObservation,
    TelemetryBook,
    TelemetryCapacityExceeded,
    TelemetryLimits,
)


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

    def test_telemetry_capacity_failure_is_transactional_and_fail_closed(self):
        telemetry = TelemetryBook(
            limits=TelemetryLimits(max_nodes=2, max_queries=2, max_incidents=1, max_tasks=1)
        )
        with self.assertRaises(TelemetryCapacityExceeded):
            telemetry.record_query(
                task_id="task-1",
                intent="missing resource",
                opportunity_key="op-1",
                selected_nodes=("events",),
                records=(),
            )
        self.assertEqual(telemetry.queries, [])
        self.assertEqual(telemetry.incidents, [])
        self.assertEqual(telemetry.node_stats, {})

        telemetry.record_task(TaskObservation("task-1", "collect", True, 1.0))
        telemetry.record_task(TaskObservation("task-1", "collect", True, 1.0))
        self.assertEqual(len(telemetry.tasks), 1)
        with self.assertRaises(TelemetryCapacityExceeded):
            telemetry.record_task(TaskObservation("task-2", "collect", True, 1.0))

    def test_telemetry_duplicate_task_lookup_uses_identity_index(self):
        telemetry = TelemetryBook(
            limits=TelemetryLimits(max_nodes=2, max_queries=2, max_incidents=2, max_tasks=4096)
        )
        for index in range(2048):
            telemetry.record_task(TaskObservation(f"task-{index}", "family", True, 1.0))
        before = tuple(telemetry.tasks)
        telemetry.record_task(before[1024])
        self.assertEqual(tuple(telemetry.tasks), before)
        with self.assertRaisesRegex(ValueError, "outcome drift"):
            telemetry.record_task(TaskObservation("task-1024", "family", False, 0.0))

    def test_telemetry_restore_rejects_snapshot_over_local_capacity_before_mutation(self):
        source = TelemetryBook(limits=TelemetryLimits(max_nodes=4, max_queries=4, max_incidents=4, max_tasks=4))
        source.record_query(
            task_id="task-1",
            intent="oak",
            opportunity_key=None,
            selected_nodes=("events",),
            records=(QueryRecordObservation("events", "r1", 1.0, {"value": "oak"}, ("e1",)),),
        )
        snapshot = source.snapshot()
        target = TelemetryBook(limits=TelemetryLimits(max_nodes=4, max_queries=1, max_incidents=4, max_tasks=4))
        target.record_query(
            task_id="existing", intent="x", opportunity_key=None, selected_nodes=(), records=()
        )
        source.record_query(
            task_id="task-2", intent="birch", opportunity_key=None, selected_nodes=(), records=()
        )
        oversized = source.snapshot()
        before = target.snapshot()
        with self.assertRaises(TelemetryCapacityExceeded):
            target.restore(oversized)
        self.assertEqual(target.snapshot(), before)
        self.assertEqual(snapshot.queries[0].task_id, "task-1")

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
