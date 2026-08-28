#!/usr/bin/env python3
"""Export only a verified T2B_GATE_PASS run into an evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_level_name(value: object) -> str:
    level_name = str(value).strip()
    if not level_name or Path(level_name).name != level_name or level_name in {".", ".."}:
        raise SystemExit("gate result contains an unsafe level_name")
    return level_name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-result", type=Path, required=True)
    parser.add_argument("--server-workdir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    gate_path = args.gate_result.resolve()
    workdir = args.server_workdir.resolve()
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("status") != "T2B_GATE_PASS" or gate.get("failure_class") != "NONE":
        raise SystemExit("only T2B_GATE_PASS with failure_class=NONE is exportable")
    level_name = _safe_level_name((gate.get("server_identity") or {}).get("level_name", ""))
    required = [gate_path, workdir / "server.log", workdir / "server.properties", workdir / "eula.txt", workdir / level_name / "level.dat"]
    required.extend(workdir / f"seed-{seed}" / "T2B_SEED_RESULT.json" for seed in ("C", "X"))
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise SystemExit("evidence members missing or empty: " + "; ".join(missing))
    member_rows = [(gate_path, "T2B_GATE_RESULT.json")]
    member_rows.extend(
        (path, path.relative_to(workdir).as_posix())
        for path in required
        if path != gate_path
    )
    manifest = {archive_name: _sha256(path) for path, archive_name in member_rows}
    bundle_manifest = {
        "schema": "t2b-evidence-v2",
        "gate_result": gate,
        "members": manifest,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bundle_manifest.json", json.dumps(bundle_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        for path, archive_name in member_rows:
            archive.write(path, archive_name)
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(_sha256(args.output) + "  " + args.output.name + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
