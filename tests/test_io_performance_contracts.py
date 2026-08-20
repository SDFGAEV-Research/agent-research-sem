from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

from research_platform.reliability.forensics.providers import HashChainError, HashChainedJSONL
import research_platform.reliability.forensics.providers.hashlog as hashlog_module
from research_platform.platform.kernel import ExecutionContext
from research_platform.observability.telemetry.metric.composition import build_default_registry
from research_platform.observability.telemetry.metric.providers import TelemetrySQLiteBackend
from research_platform.observability.telemetry.metric.runtime import TelemetryBatchRecorder, TelemetryStore


class IOPerformanceContractTests(unittest.TestCase):
    def test_hash_append_scans_once_not_once_per_row(self):
        with tempfile.TemporaryDirectory() as td:
            log=HashChainedJSONL(Path(td)/"x.jsonl",fsync_every=64)
            original=hashlog_module.scan_hash_chain
            with mock.patch.object(hashlog_module,"scan_hash_chain",wraps=original) as scan:
                for i in range(200): log.append({"i":i})
                self.assertEqual(scan.call_count,1)
            self.assertEqual(log.cached_tail[0],200)
            self.assertEqual(log.verify()[0],200)

    def test_external_same_lifetime_mutation_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.jsonl"; log=HashChainedJSONL(p); log.append({"i":1})
            # Valid external append from another writer is still an ownership violation.
            other=HashChainedJSONL(p); other.append({"i":2})
            with self.assertRaises(HashChainError): log.append({"i":3})

    def test_batch_telemetry_writes_one_transaction_per_batch(self):
        with tempfile.TemporaryDirectory() as td:
            store=TelemetryStore(build_default_registry(), TelemetrySQLiteBackend(Path(td)/"m.sqlite3")); ctx=ExecutionContext(run_id="r",trace_id="t",span_id="s")
            with TelemetryBatchRecorder(store,batch_size=100) as rec:
                for _ in range(1000): rec.observe(ctx,"llm.tokens.input",1,role="planner",model="m")
                self.assertEqual(rec.buffered,0)
            self.assertEqual(store.count(),1000)
            rows=store.query(run_id="r",metric="llm.tokens.input",limit=1001); self.assertEqual(len(rows),1000); self.assertEqual(rows[0]["sequence"],1); self.assertEqual(rows[-1]["sequence"],1000)

    def test_batch_is_retained_if_commit_fails(self):
        with tempfile.TemporaryDirectory() as td:
            store=TelemetryStore(build_default_registry(), TelemetrySQLiteBackend(Path(td)/"m.sqlite3")); ctx=ExecutionContext(run_id="r",trace_id="t",span_id="s"); rec=TelemetryBatchRecorder(store,batch_size=10)
            for _ in range(3): rec.observe(ctx,"llm.tokens.input",1,role="planner",model="m")
            with mock.patch.object(rec._session,"insert_many",side_effect=OSError("disk failure")):
                with self.assertRaises(OSError): rec.flush()
            self.assertEqual(rec.buffered,3); self.assertEqual(store.count(),0)

if __name__=='__main__': unittest.main()
