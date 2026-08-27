from pathlib import Path
import tempfile
import unittest

from tests._concurrency_support import OwnedForensicStore as ForensicStore, owned_task_group
from research_platform.observability.api import EventEnvelope
from research_platform.reliability.forensics.composition import inspect_index_freshness, rebuild_forensic_index
from research_platform.reliability.forensics.providers import ForensicWriterBusy
from research_platform.platform.kernel import ExecutionContext

class ForensicIndexV23Tests(unittest.TestCase):
    def ctx(self): return ExecutionContext('r','t','s')

    def test_index_cut_matches_authoritative_tail_after_normal_append(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); store=ForensicStore(root); store.append_event(EventEnvelope('e1', 'x', self.ctx(), 'c')); store.flush_projections()
            report=inspect_index_freshness(root); self.assertTrue(report.fresh); self.assertEqual(report.authoritative,report.indexed); store.close()

    def test_direct_authoritative_append_makes_index_stale_and_rebuild_repairs_it(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); store=ForensicStore(root); store.append_event(EventEnvelope('e1', 'x', self.ctx(), 'c')); store.flush_projections()
            # Simulates crash cut: authoritative append persisted, process died before index update.
            store.events.append(EventEnvelope('e2', 'x', self.ctx(), 'c').to_dict())
            self.assertFalse(inspect_index_freshness(root).fresh)
            store.close(); report=rebuild_forensic_index(root, task_group=owned_task_group("forensic-rebuild")); self.assertEqual(report.objects,2); self.assertTrue(inspect_index_freshness(root).fresh)
            ro=ForensicStore(root,read_only=True); self.assertEqual(ro.index.locate('e2')['event_id'],'e2')

    def test_rebuild_refuses_while_runtime_writer_lease_is_held(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); store=ForensicStore(root); store.append_event(EventEnvelope('e1', 'x', self.ctx(), 'c'))
            with self.assertRaises(ForensicWriterBusy): rebuild_forensic_index(root, task_group=owned_task_group("forensic-rebuild"))
            store.close()

if __name__=='__main__': unittest.main()
