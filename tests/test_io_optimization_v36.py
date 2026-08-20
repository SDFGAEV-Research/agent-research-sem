from pathlib import Path
import tempfile, unittest
from unittest import mock
from research_platform.platform.kernel import ExecutionContext
from research_platform.runtime.process.capture import SegmentedByteCapture
from research_platform.observability.telemetry.metric.composition import build_default_registry
from research_platform.observability.telemetry.metric.providers import TelemetrySQLiteBackend
from research_platform.observability.telemetry.metric.runtime import TelemetryBatchRecorder, TelemetryStore

class IOOptimizationV36Tests(unittest.TestCase):
    def test_capture_uses_cached_active_size_across_many_appends(self):
        with tempfile.TemporaryDirectory() as td:
            cap=SegmentedByteCapture(Path(td),'stdout',max_segment_bytes=1024*1024)
            for _ in range(100): cap.append(b'x'*100)
            self.assertEqual(cap.seal().total_bytes,10000)
    def test_batch_recorder_reuses_single_writer_session(self):
        with tempfile.TemporaryDirectory() as td:
            backend=TelemetrySQLiteBackend(Path(td)/'m.sqlite3'); store=TelemetryStore(build_default_registry(), backend); ctx=ExecutionContext(run_id='r',trace_id='t',span_id='s')
            original=backend.connect
            with mock.patch.object(backend,'connect',wraps=original) as connect:
                with TelemetryBatchRecorder(store,batch_size=10) as rec:
                    for _ in range(100): rec.observe(ctx,'llm.tokens.input',1,role='planner',model='m')
                # one writer connection for the recorder; no connection per batch
                self.assertEqual(connect.call_count,1)
            self.assertEqual(store.count(),100)

if __name__=='__main__': unittest.main()
