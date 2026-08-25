#!/usr/bin/env python3
"""Verify T2B evidence integrity and persistent-world requirements."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_level_name(value: object) -> str | None:
    level_name = str(value).strip()
    if not level_name or Path(level_name).name != level_name or level_name in {".", ".."}:
        return None
    return level_name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--source-tree-digest")
    args = parser.parse_args(argv)
    errors: list[str] = []
    try:
        with zipfile.ZipFile(args.bundle) as archive:
            names = set(archive.namelist())
            if "bundle_manifest.json" not in names or "T2B_GATE_RESULT.json" not in names:
                errors.append("bundle manifest or gate result is missing")
            manifest = json.loads(archive.read("bundle_manifest.json"))
            gate = json.loads(archive.read("T2B_GATE_RESULT.json"))
            if manifest.get("schema") != "t2b-evidence-v2":
                errors.append("unsupported evidence schema")
            if gate.get("status") != "T2B_GATE_PASS" or gate.get("failure_class") != "NONE":
                errors.append("gate result is not a PASS")
            if gate.get("same_server_process_for_both_seeds") is not True:
                errors.append("same-server-process invariant is false")
            identity = gate.get("server_identity") or {}
            level_name = _safe_level_name(identity.get("level_name", ""))
            if level_name is None:
                errors.append("server identity contains an unsafe level name")
                level_name = "__invalid_level_name__"
            for required in ("server.log", "server.properties", "eula.txt", f"{level_name}/level.dat", "seed-C/T2B_SEED_RESULT.json", "seed-X/T2B_SEED_RESULT.json"):
                if required not in names:
                    errors.append(f"missing evidence member: {required}")
            if "eula.txt" in names and b"eula=true" not in archive.read("eula.txt").lower():
                errors.append("eula.txt does not record explicit acceptance")
            for seed in ("C", "X"):
                name = f"seed-{seed}/T2B_SEED_RESULT.json"
                if name in names:
                    result = json.loads(archive.read(name))
                    if result.get("status") != "PASS":
                        errors.append(f"Seed-{seed} result is not PASS")
                    if result.get("spawned") is not True:
                        errors.append(f"Seed-{seed} bridge was not spawned")
                    if not isinstance(result.get("grounded_record_count"), int) or result["grounded_record_count"] <= 0:
                        errors.append(f"Seed-{seed} has no grounded records")
                    refs = result.get("materialized_source_refs")
                    if not isinstance(refs, list) or not refs or any(not str(ref).startswith("j_mem:") for ref in refs):
                        errors.append(f"Seed-{seed} source_refs are not grounded in J_mem")
            for name, expected in (manifest.get("members") or {}).items():
                if name not in names:
                    errors.append(f"manifest member is missing: {name}")
                elif _sha256_bytes(archive.read(name)) != expected:
                    errors.append(f"member digest mismatch: {name}")
            if args.source_tree_digest is not None and identity.get("source_tree_digest") not in (None, args.source_tree_digest):
                errors.append("source tree digest mismatch")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        errors.append(f"bundle unreadable: {type(exc).__name__}: {exc}")
    result = {"ok": not errors, "errors": errors}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
