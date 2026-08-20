from __future__ import annotations

from research_platform.governance.release.runtime.pipeline import ReleasePipeline

from .release_quality import ReleaseQualityEvidenceProvider


def build_release_pipeline() -> ReleasePipeline:
    """Bind release runtime to platform-owned quality evidence providers."""

    return ReleasePipeline(quality=ReleaseQualityEvidenceProvider())


__all__ = ["build_release_pipeline"]
