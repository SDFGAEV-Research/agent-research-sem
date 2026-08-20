from __future__ import annotations

from pathlib import Path

from research_platform.governance.architecture import build_architecture_report
from research_platform.governance.quality import scan_no_degradation, scan_silent_failures
from research_platform.governance.release.api import ReleaseQualityEvidence


def build_release_quality_evidence(root: Path) -> ReleaseQualityEvidence:
    """Project architecture/quality subsystems into a release-domain evidence contract."""

    root = Path(root).resolve()
    architecture = build_architecture_report(root)
    silent = len(scan_silent_failures(root / "research_platform"))
    methods = root / "methods"
    if methods.exists():
        silent += len(scan_silent_failures(methods))
    return ReleaseQualityEvidence(
        architecture_report_sha256=architecture.report_sha256,
        architecture_clean=architecture.clean,
        no_degradation_findings=len(scan_no_degradation(root)),
        silent_failure_findings=silent,
    )


class ReleaseQualityEvidenceProvider:
    """Composition-bound provider for the release API quality port."""

    def build(self, root: Path) -> ReleaseQualityEvidence:
        return build_release_quality_evidence(root)


__all__ = ["ReleaseQualityEvidenceProvider", "build_release_quality_evidence"]
