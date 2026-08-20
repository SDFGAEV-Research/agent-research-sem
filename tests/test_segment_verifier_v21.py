from pathlib import Path
import tempfile
import unittest
from research_platform.reliability.forensics.providers import SegmentedHashChainedJSONL
from research_platform.reliability.forensics.providers.segment_verifier import scan_segment_chain

class SegmentVerifierV21Tests(unittest.TestCase):
    def test_pure_scanner_matches_writer_tail_without_manifest_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'events'; log=SegmentedHashChainedJSONL(root,max_segment_bytes=220)
            for i in range(30): log.append({'i':i,'x':'y'*20})
            self.assertFalse((root/'manifest.json').exists())
            result=scan_segment_chain(root); self.assertEqual(result.total_rows,30); self.assertEqual(result.tail_hash,log.cached_tail[1]); self.assertFalse((root/'manifest.json').exists())
if __name__=='__main__': unittest.main()
