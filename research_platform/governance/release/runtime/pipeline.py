from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from research_platform.governance.release.runtime.evidence import (
    RELEASE_EVIDENCE_FILENAME,
    load_release_evidence,
    verify_release_evidence,
)
from research_platform.governance.release.runtime.manifest import verify_release_manifest
from research_platform.governance.release.runtime.manifest_io import load_release_manifest
from research_platform.governance.release.runtime.package_verification import verify_release_package
from research_platform.governance.release.runtime.packager import ReleasePackager
from research_platform.governance.release.runtime.project_metadata import load_project_metadata
from research_platform.governance.release.api import ReleaseQualityEvidencePort


@dataclass(frozen=True, slots=True)
class ReleasePipelineResult:
    zip_path: str
    sha256: str
    manifest_digest: str
    evidence_digest: str
    file_count: int


class ReleasePipeline:
    """Orchestrates release lifecycle. Providers stay below this layer."""

    def __init__(self, quality: ReleaseQualityEvidencePort) -> None:
        self._quality = quality

    def build(self, root: Path) -> ReleasePipelineResult:
        evidence = load_release_evidence(root / RELEASE_EVIDENCE_FILENAME)
        manifest = load_release_manifest(root / "RELEASE_MANIFEST.json")
        errors = list(verify_release_manifest(root, manifest))
        if evidence.release_manifest_digest != manifest.digest():
            errors.append("release evidence does not bind RELEASE_MANIFEST.json")
        errors.extend(verify_release_evidence(root, evidence, quality=self._quality.build(root)))
        if errors:
            raise RuntimeError("; ".join(errors))

        metadata = load_project_metadata(root, allow_unversioned=False)
        output = root.parent / f"{metadata.name}-{metadata.version}-{manifest.digest()[:12]}-release.zip"
        package = ReleasePackager().build(root, output, evidence=evidence)
        verification = verify_release_package(Path(package.zip_path))
        if not verification.clean:
            raise RuntimeError("package verification failed: " + "; ".join(verification.errors))
        return ReleasePipelineResult(
            zip_path=str(package.zip_path),
            sha256=package.sha256,
            manifest_digest=package.manifest_digest,
            evidence_digest=package.evidence_digest,
            file_count=package.file_count,
        )
