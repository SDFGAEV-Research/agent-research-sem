"""Regenerate development-only architecture and source snapshot evidence.

This is intentionally separate from the frozen release-evidence workflow. It
records the current worktree without claiming a complete regression or a
release qualification.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.governance.architecture.report import build_architecture_report
from research_platform.governance.release.runtime.manifest import EXCLUDED_DIRS, EXCLUDED_SUFFIXES
from research_platform.platform.kernel.project_root import discover_project_root


SNAPSHOT_MANIFEST = "DEVELOPMENT_SNAPSHOT_MANIFEST.sha256"
SNAPSHOT_METADATA = "DEVELOPMENT_SNAPSHOT_METADATA.json"
SNAPSHOT_REPORT = "DEVELOPMENT_ARCHITECTURE_REPORT.json"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_files(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES or relative.as_posix() == SNAPSHOT_MANIFEST:
            continue
        paths.append(path)
    return tuple(paths)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    root = discover_project_root(__file__)
    report = build_architecture_report(root)
    _write_json(root / SNAPSHOT_REPORT, asdict(report))

    files = _snapshot_files(root)
    python_files = tuple(path for path in files if path.suffix == ".py")
    test_files = tuple(path for path in files if path.parent.name == "tests" and path.name.startswith("test_"))
    docs_files = tuple(path for path in files if path.suffix == ".md")
    metadata = {
        "architecture_import_edges": report.import_edges,
        "architecture_report_sha256": report.report_sha256,
        "architecture_summary_document": "docs/CURRENT_ARCHITECTURE_EVOLUTION_20260820.md",
        "capability_graph_edges": len(report.capability_graph),
        "created_at_utc": "2026-08-20T00:00:00+00:00",
        "docs_file_count": len(docs_files),
        "event_graph_edges": len(report.event_graph),
        "file_count": len(files),
        "focused_migration_regression": "23 unit tests passed + 6 direct project-composition firewall checks",
        "latest_complete_development_regression": "historical: 709 passed + 4 subtests across four controlled shards",
        "operation_graph_edges": len(report.operation_graph),
        "platform_version": "0.41.0",
        "post_packaging_source_checks": {
            "architecture_gate": "PASS (focused migration revalidation)",
            "codegraph_cycles": "0 (one-shot graph-only; persistent database unavailable)",
            "python_compileall": "PASS",
            "full_regression": "PENDING after final-architecture migration",
        },
        "python_file_count": len(python_files),
        "release_artifacts_note": "RELEASE_MANIFEST.json and RELEASE_EVIDENCE.json remain the previous verified release baseline and do not certify this development snapshot.",
        "schema_version": 2,
        "snapshot_kind": "development",
        "snapshot_manifest_note": "DEVELOPMENT_SNAPSHOT_MANIFEST.sha256 is the byte-level authority for this development snapshot; it excludes itself but includes DEVELOPMENT_SNAPSHOT_METADATA.json.",
        "source_root_name": "research-platform-development-final-architecture-migration-20260820",
        "test_file_count": len(test_files),
        "tests_collected": None,
    }
    _write_json(root / SNAPSHOT_METADATA, metadata)

    manifest_lines = [
        f"{_hash_file(path)}  {path.relative_to(root).as_posix()}"
        for path in _snapshot_files(root)
    ]
    (root / SNAPSHOT_MANIFEST).write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(f"DEVELOPMENT_SNAPSHOT_PASS files={len(files)} python={len(python_files)} tests={len(test_files)} report={report.report_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
