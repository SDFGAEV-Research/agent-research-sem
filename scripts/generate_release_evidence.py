from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.platform.composition.release_quality import build_release_quality_evidence
from research_platform.governance.release.runtime.evidence import (
    RELEASE_EVIDENCE_FILENAME,
    build_release_evidence,
    write_release_evidence,
)
from research_platform.governance.release.runtime.manifest import build_release_manifest
from research_platform.governance.release.runtime.manifest_io import write_release_manifest
from research_platform.governance.release.runtime.freeze_lock import ReleaseFreezeBusy, ReleaseFreezeLock
from research_platform.governance.release.runtime.regression_state import clear_regression_state, default_regression_state_path
from release_regression import run_release_regression


def _generate_locked() -> int:
    baseline_manifest = build_release_manifest(ROOT)
    regression_state_path = default_regression_state_path(ROOT)
    regression = run_release_regression(
        ROOT,
        source_manifest_digest=baseline_manifest.digest(),
        state_path=regression_state_path,
    )
    after_regression_manifest = build_release_manifest(ROOT)
    if after_regression_manifest.digest() != baseline_manifest.digest():
        print("RELEASE_EVIDENCE_FAIL: source tree changed during regression")
        return 1
    quality = build_release_quality_evidence(ROOT)
    manifest = build_release_manifest(ROOT)
    if manifest.digest() != baseline_manifest.digest():
        print("RELEASE_EVIDENCE_FAIL: source tree changed during quality verification")
        return 1
    evidence = build_release_evidence(
        ROOT,
        quality=quality,
        regression_tests_collected=regression.collected,
        regression_tests_passed=regression.passed,
        regression_tests_skipped=regression.skipped,
        regression_shard_count=regression.shard_count,
        regression_test_inventory_sha256=regression.test_inventory_sha256,
        regression_runtime_sha256=regression.runtime_sha256,
        manifest=manifest,
    )
    if not evidence.clean:
        print("RELEASE_EVIDENCE_FAIL: architecture/quality evidence is not clean")
        return 1
    write_release_manifest(ROOT / "RELEASE_MANIFEST.json", manifest)
    path = ROOT / RELEASE_EVIDENCE_FILENAME
    write_release_evidence(path, evidence)
    clear_regression_state(regression_state_path)
    print(f"RELEASE_MANIFEST={ROOT / 'RELEASE_MANIFEST.json'}")
    print(f"RELEASE_MANIFEST_SHA256={manifest.digest()}")
    print(f"RELEASE_EVIDENCE={path}")
    print(f"EVIDENCE_SHA256={evidence.digest()}")
    print(f"TESTS_COLLECTED={regression.collected}")
    print(f"TESTS_PASSED={regression.passed}")
    print(f"TESTS_SKIPPED={regression.skipped}")
    print(f"TEST_SHARDS={regression.shard_count}")
    return 0


def main() -> int:
    try:
        with ReleaseFreezeLock(ROOT):
            return _generate_locked()
    except ReleaseFreezeBusy:
        print("RELEASE_EVIDENCE_FAIL: another release freeze operation is already active")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
