from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.platform.composition.release_quality import build_release_quality_evidence
from research_platform.governance.release.runtime.evidence import RELEASE_EVIDENCE_FILENAME, load_release_evidence, verify_release_evidence
from research_platform.governance.release.runtime.manifest import verify_release_manifest
from research_platform.governance.release.runtime.manifest_io import load_release_manifest
from research_platform.governance.release.runtime.freeze_lock import ReleaseFreezeBusy, ReleaseFreezeLock


def _verify_locked() -> int:
    evidence_path = ROOT / RELEASE_EVIDENCE_FILENAME
    manifest_path = ROOT / "RELEASE_MANIFEST.json"
    if not evidence_path.exists():
        print("RELEASE_EVIDENCE_VERIFY_FAIL missing RELEASE_EVIDENCE.json")
        return 1
    if not manifest_path.exists():
        print("RELEASE_EVIDENCE_VERIFY_FAIL missing RELEASE_MANIFEST.json")
        return 1
    evidence = load_release_evidence(evidence_path)
    manifest = load_release_manifest(manifest_path)
    errors = list(verify_release_manifest(ROOT, manifest))
    if evidence.release_manifest_digest != manifest.digest():
        errors.append("release evidence does not bind RELEASE_MANIFEST.json")
    errors.extend(verify_release_evidence(ROOT, evidence, quality=build_release_quality_evidence(ROOT)))
    for error in errors:
        print(f"RELEASE_EVIDENCE_VERIFY_FAIL {error}")
    if errors:
        return 1
    print(f"RELEASE_MANIFEST_VERIFY_PASS {manifest.digest()}")
    print(f"RELEASE_EVIDENCE_VERIFY_PASS {evidence.digest()}")
    return 0


def main() -> int:
    try:
        with ReleaseFreezeLock(ROOT):
            return _verify_locked()
    except ReleaseFreezeBusy:
        print("RELEASE_EVIDENCE_VERIFY_FAIL another release freeze operation is already active")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
