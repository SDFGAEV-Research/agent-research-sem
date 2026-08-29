from pathlib import Path
import json
import tempfile
import threading
import unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.platform.kernel.durability import InterprocessLockBusy
from research_platform.observability.capture.api import RawObservationCorruptionError
from research_platform.observability.capture.providers.segment_pool import RawSegmentPool
from tests._concurrency_support import raw_observation_lake


class RawLakeV50Tests(unittest.TestCase):
    def _ctx(self, run, span):
        return ExecutionContext(run, run, span)

    def test_parallel_segments_are_independent_and_contiguous(self):
        with tempfile.TemporaryDirectory() as td:
            lake = raw_observation_lake(Path(td))
            errors = []

            def worker(run):
                try:
                    for i in range(50):
                        lake.append_once(
                            self._ctx(run, f"s{i}"),
                            "study.raw",
                            {"kind": "task", "status": "running", "i": i},
                            idempotency_key=f"{run}:{i}",
                        )
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(f"r{i}",)) for i in range(4)]
            [thread.start() for thread in threads]
            [thread.join() for thread in threads]
            self.assertEqual(errors, [])
            for i in range(4):
                self.assertEqual(lake.verify(f"r{i}", "study.raw"), ())
            lake.close()

    def test_scientific_durable_family_requires_idempotency_key(self):
        with tempfile.TemporaryDirectory() as td:
            lake = raw_observation_lake(Path(td))
            with self.assertRaisesRegex(ValueError, "requires idempotency key"):
                lake.append(
                    self._ctx("r", "s"),
                    "study.raw",
                    {"kind": "task", "status": "running"},
                )
            lake.close()

    def test_reopen_loads_idempotency_once_and_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ctx = self._ctx("r", "s")
            lake = raw_observation_lake(root)
            first = lake.append_once(
                ctx,
                "study.raw",
                {"kind": "task", "status": "running"},
                idempotency_key="k",
            )
            lake.close()
            lake2 = raw_observation_lake(root)
            second = lake2.append_once(
                ctx,
                "study.raw",
                {"kind": "task", "status": "running"},
                idempotency_key="k",
            )
            self.assertEqual(
                (first.sequence, first.record_sha256),
                (second.sequence, second.record_sha256),
            )
            self.assertEqual(len(Path(first.segment_path).read_text().splitlines()), 1)
            lake2.close()

    def test_corrupt_existing_segment_fails_closed_before_append(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = RawSegmentPool.target(root, "r", "study.raw")
            target.parent.mkdir(parents=True)
            target.write_text("{bad}\n", encoding="utf-8")
            lake = raw_observation_lake(root)
            with self.assertRaises(RawObservationCorruptionError):
                lake.append_once(
                    self._ctx("r", "s"),
                    "study.raw",
                    {"kind": "task", "status": "running"},
                    idempotency_key="corrupt-probe",
                )
            lake.close()

    def test_recovery_discards_only_incomplete_tail_and_continues_sequence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ctx = self._ctx("r", "s")
            lake = raw_observation_lake(root)
            first = lake.append_once(ctx, "study.raw", {"kind": "task", "status": "running"}, idempotency_key="first")
            lake.close()
            target = Path(first.segment_path)
            with target.open("ab") as handle:
                handle.write(b'{"sequence":2')
            reopened = raw_observation_lake(root)
            second = reopened.append_once(ctx, "study.raw", {"kind": "task", "status": "done"}, idempotency_key="second")
            self.assertEqual(second.sequence, 2)
            self.assertEqual(reopened.verify("r", "study.raw"), ())
            self.assertEqual(len(target.read_text(encoding="utf-8").splitlines()), 2)
            reopened.close()

    def test_recovery_rejects_complete_record_digest_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ctx = self._ctx("r", "s")
            lake = raw_observation_lake(root)
            receipt = lake.append_once(ctx, "study.raw", {"kind": "task", "status": "running"}, idempotency_key="tamper")
            lake.close()
            target = Path(receipt.segment_path)
            row = json.loads(target.read_text(encoding="utf-8"))
            row["payload"]["status"] = "tampered"
            target.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            reopened = raw_observation_lake(root)
            with self.assertRaises(RawObservationCorruptionError):
                reopened.append_once(ctx, "study.raw", {"kind": "task", "status": "again"}, idempotency_key="again")
            reopened.close()

    def test_append_rejects_non_finite_observation_payload_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lake = raw_observation_lake(root)
            with self.assertRaises(ValueError):
                lake.append_once(
                    self._ctx("r", "s"),
                    "study.raw",
                    {"kind": "task", "status": "running", "score": float("nan")},
                    idempotency_key="non-finite",
                )
            target = RawSegmentPool.target(root, "r", "study.raw")
            self.assertFalse(target.exists())
            lake.close()

    def test_recovery_rejects_non_finite_json_with_matching_digest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ctx = self._ctx("r", "s")
            lake = raw_observation_lake(root)
            receipt = lake.append_once(
                ctx, "study.raw", {"kind": "task", "status": "running", "score": 1.0},
                idempotency_key="first",
            )
            lake.close()
            target = Path(receipt.segment_path)
            row = json.loads(target.read_text(encoding="utf-8"))
            row["payload"]["score"] = float("nan")
            unsigned = dict(row)
            unsigned.pop("record_sha256")
            canonical = json.dumps(
                unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            import hashlib
            row["record_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            target.write_text(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            reopened = raw_observation_lake(root)
            with self.assertRaises(RawObservationCorruptionError):
                reopened.append_once(
                    ctx, "study.raw", {"kind": "task", "status": "running", "score": 2.0},
                    idempotency_key="second",
                )
            reopened.close()

    def test_recovery_rejects_duplicate_json_keys_with_same_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ctx = self._ctx("r", "s")
            lake = raw_observation_lake(root)
            receipt = lake.append_once(
                ctx, "study.raw", {"kind": "task", "status": "running"},
                idempotency_key="first",
            )
            lake.close()
            target = Path(receipt.segment_path)
            text = target.read_text(encoding="utf-8")
            original = '"family":"study.raw"'
            duplicated = '"family":"study.raw","family":"study.raw"'
            self.assertIn(original, text)
            target.write_text(text.replace(original, duplicated, 1), encoding="utf-8")
            reopened = raw_observation_lake(root)
            with self.assertRaises(RawObservationCorruptionError):
                reopened.append_once(
                    ctx, "study.raw", {"kind": "task", "status": "again"},
                    idempotency_key="second",
                )
            reopened.close()

    def test_identity_cannot_escape_persistence_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            lake = raw_observation_lake(root)
            receipt = lake.append_once(
                self._ctx(r"..\..\outside/../../escape", "s"),
                "study.raw",
                {"kind": "task", "status": "running"},
                idempotency_key="escape",
            )
            target = Path(receipt.segment_path).resolve()
            self.assertIn(root, target.parents)
            self.assertTrue(target.is_file())
            lake.close()

    def test_one_segment_has_one_live_writer_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ctx = self._ctx("r", "s")
            first = raw_observation_lake(root)
            first.append_once(ctx, "study.raw", {"kind": "task", "status": "running"}, idempotency_key="first")
            competing = raw_observation_lake(root)
            with self.assertRaises(InterprocessLockBusy):
                competing.append_once(ctx, "study.raw", {"kind": "task", "status": "competing"}, idempotency_key="competing")
            first.close()
            accepted = competing.append_once(ctx, "study.raw", {"kind": "task", "status": "resumed"}, idempotency_key="resumed")
            self.assertEqual(accepted.sequence, 2)
            competing.close()


if __name__ == "__main__":
    unittest.main()
