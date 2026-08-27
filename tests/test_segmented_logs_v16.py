from tests._concurrency_support import segmented_byte_capture
from pathlib import Path
import os
import tempfile
import unittest

from research_platform.reliability.forensics.providers import HashChainError, SegmentedHashChainedJSONL
from research_platform.runtime.process.capture import CaptureIntegrityError

class SegmentedLogsV16Tests(unittest.TestCase):
    def test_global_hash_chain_rotates_and_verifies(self):
        with tempfile.TemporaryDirectory() as td:
            log=SegmentedHashChainedJSONL(Path(td)/"events",max_segment_bytes=250,fsync_every=4)
            for i in range(50): log.append({"i":i,"payload":"x"*20})
            count,tail=log.verify(); self.assertEqual(count,50); self.assertEqual(len(tail),64); self.assertGreater(len(list((Path(td)/"events").glob("*.jsonl"))),2)

    def test_segment_tamper_reports_integrity_error(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"events"; log=SegmentedHashChainedJSONL(root,max_segment_bytes=220)
            for i in range(20): log.append({"i":i,"x":"y"*20})
            log.verify(); p=sorted(root.glob("*.jsonl"))[1]; raw=p.read_bytes(); p.write_bytes(raw.replace(b'"i":',b'"j":',1))
            with self.assertRaises(HashChainError): log.verify()

    def test_lossless_capture_rotates_and_reconstructs_600k(self):
        with tempfile.TemporaryDirectory() as td:
            data=(bytes(range(256))*2344)[:600000]; cap=segmented_byte_capture(Path(td),"stdout",max_segment_bytes=65536,fsync_every_bytes=131072)
            for i in range(0,len(data),7777): cap.append(data[i:i+7777])
            m=cap.seal(); self.assertEqual(m.total_bytes,len(data)); self.assertGreater(len(m.segments),5); self.assertEqual(cap.read_range(12345,333333),data[12345:12345+333333])

    def test_sealed_capture_detects_one_byte_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); cap=segmented_byte_capture(root,"stderr",max_segment_bytes=100); cap.append(b"a"*300); m=cap.seal(); p=root/m.segments[1].filename; raw=bytearray(p.read_bytes()); raw[0]^=1; p.write_bytes(raw)
            with self.assertRaises(CaptureIntegrityError): cap.verify()

if __name__=='__main__': unittest.main()
