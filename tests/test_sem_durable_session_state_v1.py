from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from research_platform.platform.kernel import ExecutionContext
from projects.sem_paper.composition.session_state import DurableSEMSessionStateFactory
from projects.sem_paper.composition.session_state import DurableSEMSessionStateError
from projects.sem_paper.composition.session_state import FileSEMSessionStateStore


class SEMDurableSessionStateTests(unittest.TestCase):
    def test_j_mem_and_lineage_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            factory = DurableSEMSessionStateFactory(Path(directory))
            context = ExecutionContext("run", "trace", "span", task_id="task")
            first = factory.create("session-1")
            first.ingest({"kind": "WORLD_OBSERVATION", "entity": "tree"}, context)
            first.task_completed(context)
            before = first.diagnostics()

            reopened = factory.create("session-1")
            after = reopened.diagnostics()
            self.assertEqual(after["evidence_sequence"], before["evidence_sequence"])
            self.assertEqual(after["tasks_completed"], before["tasks_completed"])
            self.assertEqual(after["evidence_digest"], before["evidence_digest"])
            self.assertEqual(
                [row.mutation_type for row in reopened.mutation_history()],
                ["INGEST", "TASK_COMPLETED"],
            )

    def test_close_flushes_without_reading_an_open_only_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            factory = DurableSEMSessionStateFactory(Path(directory))
            session = factory.create("session-2")
            session.close()
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)

    def test_concurrent_reopeners_fail_closed_on_lost_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            factory = DurableSEMSessionStateFactory(Path(directory))
            first = factory.create("session-cas")
            second = factory.create("session-cas")
            context = ExecutionContext("run", "trace", "span", task_id="task")
            first.ingest({"kind": "WORLD_OBSERVATION", "entity": "first"}, context)
            with self.assertRaises(DurableSEMSessionStateError):
                second.ingest({"kind": "WORLD_OBSERVATION", "entity": "stale"}, context)

    def test_wal_recovers_latest_snapshot_after_primary_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            factory = DurableSEMSessionStateFactory(root)
            context = ExecutionContext("run", "trace", "span", task_id="task")
            session = factory.create("session-wal")
            session.ingest({"kind": "WORLD_OBSERVATION", "entity": "tree"}, context)
            primary = next(root.glob("*.json"))
            primary.write_text("{corrupt", encoding="utf-8")

            reopened = factory.create("session-wal")
            self.assertEqual(reopened.diagnostics()["evidence_sequence"], 1)
            self.assertEqual(len(reopened.mutation_history()), 1)

    def test_complete_wal_corruption_fails_closed_but_partial_tail_is_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            factory = DurableSEMSessionStateFactory(root)
            factory.create("session-wal-corrupt")
            primary = next(root.glob("*.json"))
            wal = primary.with_name(primary.name + ".wal")
            with wal.open("a", encoding="utf-8") as handle:
                handle.write('{"schema":"broken"}\n')
            with self.assertRaises(DurableSEMSessionStateError):
                factory.create("session-wal-corrupt")

            valid_prefix = wal.read_text(encoding="utf-8").splitlines(keepends=True)[0]
            wal.write_text(valid_prefix + "{partial", encoding="utf-8")
            reopened = factory.create("session-wal-corrupt")
            self.assertEqual(reopened.diagnostics()["evidence_sequence"], 0)

    def test_repair_primary_republishes_latest_valid_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            factory = DurableSEMSessionStateFactory(root)
            factory.create("session-repair")
            primary = next(root.glob("*.json"))
            store = FileSEMSessionStateStore(primary)
            primary.write_text("not-json", encoding="utf-8")
            snapshot = store.repair_primary()
            self.assertEqual(snapshot.evidence.sequence, 0)
            self.assertEqual(store.read().evidence.sequence, 0)


if __name__ == "__main__":
    unittest.main()
