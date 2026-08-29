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

class VerifiedLedgerSliceContractTests(unittest.TestCase):
    def test_single_file_ledger_exposes_named_verified_cut(self):
        from research_platform.reliability.forensics.providers import HashChainedJSONL

        with tempfile.TemporaryDirectory() as td:
            log = HashChainedJSONL(Path(td) / "failures.jsonl")
            for index in range(5):
                log.append({"index": index})
            verified = log.verified_payloads_after(2)
            self.assertEqual(verified.start_after, 2)
            self.assertEqual(verified.total_rows, 5)
            self.assertEqual([row["index"] for row in verified.payloads], [2, 3, 4])
            self.assertEqual(verified.tail_hash, log.cached_tail[1])
            self.assertEqual(len(verified.checkpoint_hash), 64)

    def test_contract_rejects_incoherent_row_count_or_digest(self):
        from research_platform.reliability.forensics.api import VerifiedLedgerSlice

        with self.assertRaises(ValueError):
            VerifiedLedgerSlice(2, 1, "0" * 64, "0" * 64, ())
        with self.assertRaises(ValueError):
            VerifiedLedgerSlice(0, 0, "INVALID", "0" * 64, ())

if __name__=='__main__': unittest.main()
