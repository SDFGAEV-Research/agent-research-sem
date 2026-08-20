from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from research_platform.platform.kernel.durability.durable_file import (
    DurableFileWriteError,
    atomic_replace_bytes,
    durable_replace_file,
    durable_unlink,
)


class DurableFileTests(unittest.TestCase):
    def test_atomic_replace_fsyncs_parent_after_replace(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            events: list[str] = []

            from research_platform.platform.kernel.durability import durable_file as module

            real_replace = module.os.replace
            real_fsync_directory = module.fsync_directory

            def replace(src: Path, dst: Path) -> None:
                events.append("replace")
                real_replace(src, dst)

            def fsync_parent(parent: Path) -> None:
                events.append("fsync-parent")
                real_fsync_directory(parent)

            with patch.object(module.os, "replace", side_effect=replace), patch.object(
                module, "fsync_directory", side_effect=fsync_parent
            ):
                atomic_replace_bytes(path, b"v1")

            self.assertEqual(path.read_bytes(), b"v1")
            self.assertEqual(events, ["replace", "fsync-parent"])

    def test_failed_replace_does_not_leave_temp_file(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            path = root / "state.json"
            with patch(
                "research_platform.platform.kernel.durability.durable_file.os.replace",
                side_effect=OSError("replace failed"),
            ):
                with self.assertRaises(DurableFileWriteError):
                    atomic_replace_bytes(path, b"v1")

            self.assertFalse(path.exists())
            self.assertEqual(list(root.glob(".state.json.tmp.*")), [])

    def test_durable_replace_file_fsyncs_source_then_parent(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            source = root / "rebuilt.sqlite3"
            target = root / "index.sqlite3"
            source.write_bytes(b"sqlite")
            with patch(
                "research_platform.platform.kernel.durability.durable_file.fsync_directory"
            ) as sync:
                durable_replace_file(source, target)
            self.assertFalse(source.exists())
            self.assertEqual(target.read_bytes(), b"sqlite")
            sync.assert_called_once_with(root)

    def test_durable_unlink_fsyncs_parent(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            path = root / "lease.json"
            path.write_bytes(b"lease")
            with patch(
                "research_platform.platform.kernel.durability.durable_file.fsync_directory"
            ) as sync:
                durable_unlink(path)
            self.assertFalse(path.exists())
            sync.assert_called_once_with(root)


if __name__ == "__main__":
    unittest.main()
