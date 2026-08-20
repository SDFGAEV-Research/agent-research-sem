import os
import signal
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest

from scripts.release_regression import (
    ReleaseRegressionFailure,
    _parse_collected,
    _parse_result,
    _run_pytest,
)


class ReleaseRegressionV191Tests(unittest.TestCase):
    def test_collection_and_result_parsing_are_machine_checked(self):
        self.assertEqual(_parse_collected("665 tests collected in 0.5s\n"), 665)
        self.assertEqual(_parse_result("665 passed, 4 subtests passed in 30s\n"), (665, 0))
        self.assertEqual(_parse_result("660 passed, 5 skipped in 30s\n"), (660, 5))

    def test_unparseable_regression_output_fails_closed(self):
        with self.assertRaises(ReleaseRegressionFailure):
            _parse_collected("collection complete")
        with self.assertRaises(ReleaseRegressionFailure):
            _parse_result("all good")

    def test_pytest_shard_reaps_descendants_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pid_path = root / "child.pid"
            (root / "test_spawn.py").write_text(
                "import subprocess, sys\n"
                "def test_spawn():\n"
                f"    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                f"    open({str(pid_path)!r}, 'w').write(str(p.pid))\n"
                "    assert True\n",
                encoding="utf-8",
            )
            output = _run_pytest(root, ["-q"], timeout_seconds=10.0)
            self.assertIn("1 passed", output)
            child_pid = int(pid_path.read_text())
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and Path(f"/proc/{child_pid}").exists():
                stat = Path(f"/proc/{child_pid}/stat")
                if stat.exists() and stat.read_text().split()[2] == "Z":
                    break
                time.sleep(0.02)
            if Path(f"/proc/{child_pid}/stat").exists():
                self.assertEqual(Path(f"/proc/{child_pid}/stat").read_text().split()[2], "Z")

    def test_pytest_timeout_reaps_entire_process_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pid_path = root / "child.pid"
            (root / "test_spawn.py").write_text(
                "import subprocess, sys, time\n"
                f"p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                f"open({str(pid_path)!r}, 'w').write(str(p.pid))\n"
                "def test_spawn():\n"
                "    time.sleep(60)\n",
                encoding="utf-8",
            )
            with self.assertRaises(ReleaseRegressionFailure):
                _run_pytest(root, ["-q"], timeout_seconds=6.0)
            child_pid = int(pid_path.read_text())
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and Path(f"/proc/{child_pid}").exists():
                stat = Path(f"/proc/{child_pid}/stat")
                if stat.exists() and stat.read_text().split()[2] == "Z":
                    break
                time.sleep(0.02)
            if Path(f"/proc/{child_pid}/stat").exists():
                self.assertEqual(Path(f"/proc/{child_pid}/stat").read_text().split()[2], "Z")

    def test_external_runner_sigterm_reaps_active_pytest_group(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shard_pid_path = root / "shard.pid"
            (root / "test_wait.py").write_text(
                "import os, time\n"
                f"open({str(shard_pid_path)!r}, 'w').write(str(os.getpid()))\n"
                "def test_wait():\n"
                "    time.sleep(60)\n",
                encoding="utf-8",
            )
            code = (
                "from pathlib import Path; "
                "from scripts.release_regression import _run_pytest; "
                f"_run_pytest(Path({str(root)!r}), ['-q'], timeout_seconds=60)"
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(project_root)
            runner = subprocess.Popen([sys.executable, "-c", code], cwd=project_root, env=env)
            try:
                deadline = time.monotonic() + 10.0
                while time.monotonic() < deadline and not shard_pid_path.exists():
                    time.sleep(0.02)
                self.assertTrue(shard_pid_path.exists(), "pytest shard did not start")
                shard_pid = int(shard_pid_path.read_text())
                runner.send_signal(signal.SIGTERM)
                self.assertEqual(runner.wait(timeout=5.0), 128 + signal.SIGTERM)
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline and Path(f"/proc/{shard_pid}").exists():
                    stat = Path(f"/proc/{shard_pid}/stat")
                    if stat.exists() and stat.read_text().split()[2] == "Z":
                        break
                    time.sleep(0.02)
                if Path(f"/proc/{shard_pid}/stat").exists():
                    self.assertEqual(Path(f"/proc/{shard_pid}/stat").read_text().split()[2], "Z")
            finally:
                if runner.poll() is None:
                    runner.kill()
                    runner.wait()


if __name__ == "__main__":
    unittest.main()
