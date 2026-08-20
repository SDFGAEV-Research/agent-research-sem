from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scripts.release_regression as regression
from research_platform.governance.release.runtime.regression_state import default_regression_state_path


class ReleaseRegressionResumeV193Tests(unittest.TestCase):
    def _tree(self, root: Path) -> None:
        tests = root / "tests"
        tests.mkdir(parents=True)
        (tests / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
        (tests / "test_b.py").write_text("def test_b():\n    assert True\n", encoding="utf-8")

    @staticmethod
    def _fake_pytest(_root: Path, args: list[str], **_kwargs) -> str:
        if "--collect-only" in args:
            return (
                "tests/test_a.py::test_a\n"
                "tests/test_b.py::test_b\n\n"
                "2 tests collected in 0.01s\n"
            )
        if "tests/test_a.py" in args or "tests/test_b.py" in args:
            return ". [100%]\n1 passed in 0.01s\n"
        raise AssertionError(f"unexpected pytest args: {args}")

    def test_completed_shards_resume_without_reexecution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"; root.mkdir(); self._tree(root)
            state_path = default_regression_state_path(root)
            with patch.object(regression, "_run_pytest", side_effect=self._fake_pytest):
                first = regression.run_release_regression(
                    root,
                    source_manifest_digest="a" * 64,
                    shard_size=1,
                    state_path=state_path,
                )

            calls: list[tuple[str, ...]] = []
            def collect_only(root_arg, args, **kwargs):
                calls.append(tuple(args))
                if "--collect-only" not in args:
                    raise AssertionError("completed shard was re-executed")
                return self._fake_pytest(root_arg, args, **kwargs)

            with patch.object(regression, "_run_pytest", side_effect=collect_only):
                resumed = regression.run_release_regression(
                    root,
                    source_manifest_digest="a" * 64,
                    shard_size=1,
                    state_path=state_path,
                )
            self.assertEqual(resumed, first)
            self.assertEqual(len(calls), 1)

    def test_source_manifest_change_invalidates_cached_shards(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"; root.mkdir(); self._tree(root)
            state_path = default_regression_state_path(root)
            with patch.object(regression, "_run_pytest", side_effect=self._fake_pytest):
                regression.run_release_regression(
                    root,
                    source_manifest_digest="a" * 64,
                    shard_size=1,
                    state_path=state_path,
                )

            shard_runs: list[tuple[str, ...]] = []
            def track(root_arg, args, **kwargs):
                if "--collect-only" not in args:
                    shard_runs.append(tuple(args))
                return self._fake_pytest(root_arg, args, **kwargs)

            with patch.object(regression, "_run_pytest", side_effect=track):
                regression.run_release_regression(
                    root,
                    source_manifest_digest="b" * 64,
                    shard_size=1,
                    state_path=state_path,
                )
            self.assertEqual(len(shard_runs), 2)

    def test_corrupt_resume_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"; root.mkdir(); self._tree(root)
            state_path = default_regression_state_path(root)
            state_path.write_bytes(b"not-json")
            with patch.object(regression, "_run_pytest", side_effect=self._fake_pytest):
                with self.assertRaises(regression.ReleaseRegressionFailure):
                    regression.run_release_regression(
                        root,
                        source_manifest_digest="a" * 64,
                        shard_size=1,
                        state_path=state_path,
                    )


if __name__ == "__main__":
    unittest.main()
