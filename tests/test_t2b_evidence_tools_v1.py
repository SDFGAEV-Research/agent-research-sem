from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class T2BEvidenceToolTests(unittest.TestCase):
    def test_export_and_verify_bind_actual_archive_member_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); workdir = root / "server"; workdir.mkdir()
            (workdir / "server.log").write_text("real server log\n", encoding="utf-8")
            (workdir / "server.properties").write_text("level-name=t2b-world\n", encoding="utf-8")
            (workdir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
            (workdir / "t2b-world").mkdir(); (workdir / "t2b-world" / "level.dat").write_bytes(b"real-level")
            for seed in ("C", "X"):
                seed_dir = workdir / f"seed-{seed}"; seed_dir.mkdir()
                (seed_dir / "T2B_SEED_RESULT.json").write_text(json.dumps({
                    "status": "PASS", "spawned": True, "grounded_record_count": 1,
                    "materialized_source_refs": [f"j_mem:{seed}:1"],
                }), encoding="utf-8")
            gate_path = root / "T2B_GATE_RESULT.json"
            gate_path.write_text(json.dumps({
                "schema": "t2b-gate.v2", "status": "T2B_GATE_PASS", "failure_class": "NONE",
                "same_server_process_for_both_seeds": True,
                "server_identity": {"level_name": "t2b-world", "pid": 1234},
            }), encoding="utf-8")
            bundle = root / "evidence.zip"
            export = subprocess.run([sys.executable, str(ROOT / "scripts/t2b_export_evidence.py"), "--gate-result", str(gate_path), "--server-workdir", str(workdir), "--output", str(bundle)], check=False, capture_output=True, text=True)
            self.assertEqual(export.returncode, 0, export.stderr)
            verify = subprocess.run([sys.executable, str(ROOT / "scripts/t2b_verify_evidence.py"), str(bundle)], check=False, capture_output=True, text=True)
            self.assertEqual(verify.returncode, 0, verify.stdout)
            with zipfile.ZipFile(bundle) as archive:
                members = json.loads(archive.read("bundle_manifest.json"))["members"]
            self.assertIn("server.log", members); self.assertIn("T2B_GATE_RESULT.json", members)


if __name__ == "__main__":
    unittest.main()
