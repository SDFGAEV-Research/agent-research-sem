from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_platform.reliability.forensics.providers.segmented_hashlog import SegmentedHashChainedJSONL


class SegmentedEventHotPathV173Tests(unittest.TestCase):
    def test_steady_state_append_does_not_enumerate_all_segments(self) -> None:
        with TemporaryDirectory() as td:
            ledger = SegmentedHashChainedJSONL(
                Path(td) / "events",
                max_segment_bytes=128,
                fsync_every=4,
            )
            # First append initializes/verifies the writer state.
            ledger.append({"event": 0, "payload": "x" * 100})
            # Force multiple rotations so an O(segment-count) check would be visible.
            for value in range(1, 8):
                ledger.append({"event": value, "payload": "x" * 100})
            with patch.object(
                ledger,
                "_segment_files",
                side_effect=AssertionError("steady-state append enumerated segment directory"),
            ):
                ledger.append({"event": 9, "payload": "hot"})

    def test_external_segment_directory_change_still_fails_closed(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td) / "events"
            ledger = SegmentedHashChainedJSONL(root, fsync_every=4)
            ledger.append({"event": 1})
            (root / "99999999.jsonl").write_text("", encoding="utf-8")
            with self.assertRaises(Exception):
                ledger.append({"event": 2})


if __name__ == "__main__":
    unittest.main()
