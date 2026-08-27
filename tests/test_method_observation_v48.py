from research_platform.platform.composition.method_telemetry_sink import RawLakeMethodObservationSink
from pathlib import Path
import json, tempfile, unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodObservation
from tests._concurrency_support import raw_observation_lake


class MethodObservationV48Tests(unittest.TestCase):
    def test_raw_lake_adapter_keeps_exact_method_mutation_identity(self):
        with tempfile.TemporaryDirectory() as td:
            lake=raw_observation_lake(Path(td))
            sink=RawLakeMethodObservationSink(lake)
            ctx=ExecutionContext('run','trace','span',task_id='task',decision_cycle_id='dc')
            receipt=sink.record(MethodObservation.build(ctx,'self_evolving_memory','s','session_mutation',{'revision':7,'after_state_digest':'abc'}))
            row=json.loads(Path(receipt.segment_path).read_text().splitlines()[0])
            self.assertEqual(row['payload']['method'],'self_evolving_memory')
            self.assertEqual(row['payload']['revision'],7)
            self.assertEqual(row['context']['decision_cycle_id'],'dc')
            self.assertEqual(lake.verify('run','method.raw'),())
            second=sink.record(MethodObservation.build(ctx,'self_evolving_memory','s','session_mutation',{'revision':7,'after_state_digest':'abc'}))
            self.assertEqual(second.sequence,receipt.sequence)
            self.assertEqual(len(Path(receipt.segment_path).read_text().splitlines()),1)

if __name__=='__main__': unittest.main()
