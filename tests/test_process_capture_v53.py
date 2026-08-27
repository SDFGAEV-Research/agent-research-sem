from tests._concurrency_support import process_capture
from pathlib import Path
import tempfile, unittest

from tests._concurrency_support import segmented_byte_capture


class ProcessCaptureV53Tests(unittest.TestCase):
    def test_rotation_receipt_and_hot_tail(self):
        with tempfile.TemporaryDirectory() as td:
            cap=segmented_byte_capture(Path(td),'stdout',max_segment_bytes=10,fsync_every_bytes=100,tail_bytes=16)
            rotations=cap.append(b'abcdefghijklmnopqrstuvwxyz')
            self.assertEqual([(r.from_index,r.to_index) for r in rotations],[(0,1),(1,2)])
            self.assertEqual(cap.tail(),b'klmnopqrstuvwxyz')
            receipt=cap.sync(); self.assertEqual(receipt.total_bytes,26); self.assertEqual(len(receipt.tail_sha256),64)
            cap.close()

    def test_reopen_recovers_tail_and_continues_append(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); cap=segmented_byte_capture(root,'stderr',tail_bytes=8); cap.append(b'1234567890'); cap.sync(); cap.close()
            cap2=segmented_byte_capture(root,'stderr',tail_bytes=8); self.assertEqual(cap2.tail(),b'34567890'); cap2.append(b'AB'); self.assertEqual(cap2.tail(),b'567890AB'); self.assertEqual(cap2.seal().total_bytes,12)

if __name__=='__main__': unittest.main()
