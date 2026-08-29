from pathlib import Path
import math
import sqlite3
import tempfile
import unittest

from tests._concurrency_support import telemetry_backend
from research_platform.platform.kernel import ExecutionContext
from research_platform.observability.telemetry.metric.api import TelemetryMetricCorruptionError
from research_platform.observability.telemetry.metric.composition import build_default_registry
from research_platform.observability.telemetry.metric.runtime import TelemetryAudit, TelemetryStore


class TelemetryStoreTests(unittest.TestCase):
    def _ctx(self):
        return ExecutionContext(run_id="run_1",trace_id="trace_1",span_id="span_1",task_id="task_99",decision_cycle_id="dc_77",operation_id="op_42",component_id="llm.runtime")

    def test_default_catalog_is_broad_and_low_cardinality_clean(self):
        r=build_default_registry()
        self.assertGreaterEqual(len(r.names()),100)
        self.assertEqual(TelemetryAudit(r).run(),())

    def test_persistent_store_keeps_high_cardinality_context_outside_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            r=build_default_registry(); store=TelemetryStore(r, telemetry_backend(self, Path(td)/"metrics.sqlite3")); ctx=self._ctx()
            seq=store.observe(ctx,"llm.request.latency",0.25,role="planner",model="qwen",endpoint="local",status="success")
            self.assertEqual(seq,1); self.assertEqual(store.count(),1)
            row=store.query(run_id="run_1",decision_cycle_id="dc_77")[0]
            self.assertEqual(row["task_id"],"task_99"); self.assertEqual(row["operation_id"],"op_42")
            self.assertNotIn("task_id",row["dimensions"]); self.assertEqual(row["dimensions"]["role"],"planner")

    def test_nonfinite_negative_counter_and_bad_ratio_are_rejected(self):
        r=build_default_registry(); ctx=self._ctx()
        with tempfile.TemporaryDirectory() as td:
            store=TelemetryStore(r, telemetry_backend(self, Path(td)/"m.sqlite3"))
            with self.assertRaises(ValueError): store.observe(ctx,"llm.request.latency",math.nan,role="planner",model="m",endpoint="e",status="x")
            with self.assertRaises(ValueError): store.observe(ctx,"llm.tokens.input",-1,role="planner",model="m")
            with self.assertRaises(ValueError): store.observe(ctx,"gpu.utilization",1.2,gpu="0",model_service="s")
            self.assertEqual(store.count(),0)

    def test_reader_connection_has_no_write_authority(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "m.sqlite3"
            backend = telemetry_backend(self, path)
            store = TelemetryStore(build_default_registry(), backend)
            store.observe(self._ctx(), "llm.tokens.input", 1, role="planner", model="m")
            with backend.reader_session() as reader:
                self.assertEqual(reader.db.execute("PRAGMA query_only").fetchone()[0], 1)
                with self.assertRaises(sqlite3.OperationalError):
                    reader.db.execute("DELETE FROM metric_observations")

    def test_persisted_metric_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "m.sqlite3"
            store = TelemetryStore(build_default_registry(), telemetry_backend(self, path))
            store.observe(self._ctx(), "llm.tokens.input", 1, role="planner", model="m")
            db = sqlite3.connect(path)
            try:
                with db:
                    db.execute("UPDATE metric_observations SET dimensions_json='1'")
            finally:
                db.close()
            with self.assertRaises(TelemetryMetricCorruptionError):
                store.query(run_id="run_1")

    def test_persisted_metric_scalar_type_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "m.sqlite3"
            store = TelemetryStore(build_default_registry(), telemetry_backend(self, path))
            store.observe(self._ctx(), "llm.tokens.input", 1, role="planner", model="m")
            db = sqlite3.connect(path)
            try:
                with db:
                    db.execute("UPDATE metric_observations SET value='not-a-number'")
            finally:
                db.close()
            with self.assertRaises(TelemetryMetricCorruptionError):
                store.query(run_id="run_1")

    def test_high_card_id_still_rejected_as_metric_dimension(self):
        r=build_default_registry(); ctx=self._ctx()
        with tempfile.TemporaryDirectory() as td:
            store=TelemetryStore(r, telemetry_backend(self, Path(td)/"m.sqlite3"))
            with self.assertRaises(ValueError):
                store.observe(ctx,"operation.latency",1.0,component="c",operation="o",status="ok",request_id="r1")

if __name__ == "__main__": unittest.main()
