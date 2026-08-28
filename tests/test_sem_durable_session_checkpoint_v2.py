from __future__ import annotations

import threading
import time
import unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import RecallRequest
from research_platform.participant.method.runtime import InMemoryMethodObservationSink
from research_platform.participant.method.api import MethodServices
from projects.sem_paper.method.self_evolving_memory.session import SEMSessionRestoreFaulted
from sem_test_support import build_fixed_memory_method


class SEMDurableSessionCheckpointV2Tests(unittest.TestCase):
    @staticmethod
    def _services() -> MethodServices:
        return MethodServices(InMemoryMethodObservationSink())

    def test_checkpoint_is_one_method_cut_against_concurrent_ingest(self) -> None:
        method = build_fixed_memory_method()
        session = method.open_session(session_id="s", services=self._services())
        context = ExecutionContext("run", "trace", "span")

        entered = threading.Event()
        release = threading.Event()
        ingest_done = threading.Event()
        snapshots = []
        errors: list[BaseException] = []

        cell = session._runtime.persistence._cell
        original_snapshot = cell.snapshot_state

        def blocked_snapshot():
            entered.set()
            if not release.wait(timeout=5):
                raise TimeoutError("checkpoint test barrier timed out")
            return original_snapshot()

        cell.snapshot_state = blocked_snapshot

        def take_checkpoint() -> None:
            try:
                snapshots.append(session.checkpoint())
            except BaseException as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        def ingest() -> None:
            try:
                session.ingest({"value": 1}, context)
                ingest_done.set()
            except BaseException as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        checkpoint_thread = threading.Thread(target=take_checkpoint)
        checkpoint_thread.start()
        self.assertTrue(entered.wait(timeout=2))

        ingest_thread = threading.Thread(target=ingest)
        ingest_thread.start()
        time.sleep(0.05)
        self.assertFalse(ingest_done.is_set(), "ingest crossed the checkpoint session barrier")

        release.set()
        checkpoint_thread.join(timeout=5)
        ingest_thread.join(timeout=5)
        self.assertFalse(checkpoint_thread.is_alive())
        self.assertFalse(ingest_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(session.diagnostics()["evidence_sequence"], 1)

        restored = method.open_session(session_id="s", services=self._services())
        restored.restore(snapshots[0])
        self.assertEqual(restored.diagnostics()["evidence_sequence"], 0)

    def test_apply_failure_faults_session_and_blocks_scientific_reuse(self) -> None:
        method = build_fixed_memory_method()
        context = ExecutionContext("run", "trace", "span", task_id="task")
        source = method.open_session(session_id="s", services=self._services())
        source.ingest({"value": 1}, context)
        source.task_completed({}, context)
        snapshot = source.checkpoint()

        target = method.open_session(session_id="s", services=self._services())
        persistence = target._runtime.persistence
        original_restore = persistence._tasks.restore

        def partial_restore(rows) -> None:
            original_restore(rows)
            raise OSError("injected restore apply failure")

        persistence._tasks.restore = partial_restore
        with self.assertRaisesRegex(OSError, "injected restore apply failure"):
            target.restore(snapshot)

        fault = target.diagnostics()["restore_fault"]
        self.assertIsNotNone(fault)
        self.assertEqual(fault["error_type"], "OSError")
        self.assertEqual(len(fault["error_digest"]), 64)

        with self.assertRaises(SEMSessionRestoreFaulted):
            target.ingest({"after": "fault"}, context)
        with self.assertRaises(SEMSessionRestoreFaulted):
            target.recall(RecallRequest("anything", context))
        with self.assertRaises(SEMSessionRestoreFaulted):
            target.checkpoint()
        with self.assertRaises(SEMSessionRestoreFaulted):
            _ = target.generation

        # Forensic reads and cleanup remain available after fail-closed fencing.
        target.mutation_history()
        target.close()

    def test_prepare_failure_does_not_poison_unchanged_session(self) -> None:
        method = build_fixed_memory_method()
        context = ExecutionContext("run", "trace", "span")
        source = method.open_session(session_id="other", services=self._services())
        snapshot = source.checkpoint()

        target = method.open_session(session_id="s", services=self._services())
        with self.assertRaisesRegex(ValueError, "different session"):
            target.restore(snapshot)
        self.assertIsNone(target.diagnostics()["restore_fault"])

        target.ingest({"still": "usable"}, context)
        self.assertEqual(target.diagnostics()["evidence_sequence"], 1)


if __name__ == "__main__":
    unittest.main()
