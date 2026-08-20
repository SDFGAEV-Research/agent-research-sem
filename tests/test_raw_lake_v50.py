from pathlib import Path
import tempfile, threading, unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.observability.capture.api import RawObservationCorruptionError
from research_platform.observability.capture.composition import build_file_raw_observation_lake


class RawLakeV50Tests(unittest.TestCase):
    def _ctx(self,run,span): return ExecutionContext(run,run,span)

    def test_parallel_segments_are_independent_and_contiguous(self):
        with tempfile.TemporaryDirectory() as td:
            lake=build_file_raw_observation_lake(Path(td)); errors=[]
            def worker(run):
                try:
                    for i in range(50): lake.append(self._ctx(run,f's{i}'),'study.raw',{'kind':'task','status':'running','i':i})
                except Exception as exc: errors.append(exc)
            ts=[threading.Thread(target=worker,args=(f'r{i}',)) for i in range(4)]
            [t.start() for t in ts]; [t.join() for t in ts]
            self.assertEqual(errors,[])
            for i in range(4): self.assertEqual(lake.verify(f'r{i}','study.raw'),())
            lake.close()

    def test_reopen_loads_idempotency_once_and_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); ctx=self._ctx('r','s')
            lake=build_file_raw_observation_lake(root); a=lake.append_once(ctx,'study.raw',{'kind':'task','status':'running'},idempotency_key='k'); lake.close()
            lake2=build_file_raw_observation_lake(root); b=lake2.append_once(ctx,'study.raw',{'kind':'task','status':'running'},idempotency_key='k')
            self.assertEqual((a.sequence,a.payload_sha256),(b.sequence,b.payload_sha256)); self.assertEqual(len(Path(a.segment_path).read_text().splitlines()),1); lake2.close()

    def test_corrupt_existing_segment_fails_closed_before_append(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r'/'study_raw.jsonl'; p.parent.mkdir(parents=True); p.write_text('{bad}\n')
            lake=build_file_raw_observation_lake(Path(td))
            with self.assertRaises(RawObservationCorruptionError): lake.append(self._ctx('r','s'),'study.raw',{'kind':'task','status':'running'})
            lake.close()

if __name__=='__main__': unittest.main()
