from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.platform.kernel import canonical_digest


_HEX = frozenset("0123456789abcdef")


def _require_identity(value: str, field: str) -> None:
    if not value.strip() or "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError(f"evidence bundle {field} is invalid")


def _require_sha256(value: str, field: str) -> None:
    if len(value) != 64 or any(character not in _HEX for character in value.lower()):
        raise ValueError(f"evidence bundle {field} must be SHA-256")


class EvidenceBundleStatus(StrEnum):
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, order=True)
class EvidenceStreamDescriptor:
    stream_id: str
    family: str
    schema_version: str
    artifact_ref: str
    record_count: int
    content_sha256: str
    required: bool
    source_of_truth: bool

    def __post_init__(self) -> None:
        _require_identity(self.stream_id, "stream_id")
        if (
            not self.family.strip()
            or not self.schema_version.strip()
            or not self.artifact_ref.strip()
        ):
            raise ValueError("evidence stream identity is incomplete")
        if self.record_count < 0:
            raise ValueError("evidence stream record_count cannot be negative")
        _require_sha256(self.content_sha256, "stream content_sha256")


@dataclass(frozen=True, slots=True, order=True)
class DerivedEvidenceArtifact:
    artifact_id: str
    artifact_kind: str
    artifact_ref: str
    content_sha256: str
    derived_from_stream_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identity(self.artifact_id, "artifact_id")
        if not self.artifact_kind.strip() or not self.artifact_ref.strip():
            raise ValueError("derived evidence artifact identity is incomplete")
        _require_sha256(self.content_sha256, "artifact content_sha256")
        if not self.derived_from_stream_ids:
            raise ValueError("derived evidence artifact requires source streams")
        if tuple(sorted(set(self.derived_from_stream_ids))) != self.derived_from_stream_ids:
            raise ValueError("derived evidence source stream ids must be unique and ordered")


@dataclass(frozen=True, slots=True)
class EvidenceBundleManifest:
    """Immutable index over raw scientific streams and rebuildable projections."""

    schema_version: str
    bundle_id: str
    run_id: str
    status: EvidenceBundleStatus
    source_checkpoint_id: str | None
    streams: tuple[EvidenceStreamDescriptor, ...]
    derived_artifacts: tuple[DerivedEvidenceArtifact, ...] = ()

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("evidence bundle schema_version is required")
        _require_identity(self.bundle_id, "bundle_id")
        _require_identity(self.run_id, "run_id")
        if self.source_checkpoint_id is not None and not self.source_checkpoint_id.strip():
            raise ValueError("evidence bundle source checkpoint cannot be blank")
        if not self.streams:
            raise ValueError("evidence bundle requires at least one stream")
        stream_ids = tuple(stream.stream_id for stream in self.streams)
        if tuple(sorted(set(stream_ids))) != stream_ids:
            raise ValueError("evidence streams must be unique and ordered")
        if not any(stream.required and stream.source_of_truth for stream in self.streams):
            raise ValueError("evidence bundle requires an authoritative required stream")
        if self.status is EvidenceBundleStatus.COMPLETE and any(
            stream.required and stream.record_count == 0 for stream in self.streams
        ):
            raise ValueError("complete evidence bundle cannot have an empty required stream")
        artifact_ids = tuple(artifact.artifact_id for artifact in self.derived_artifacts)
        if tuple(sorted(set(artifact_ids))) != artifact_ids:
            raise ValueError("derived evidence artifacts must be unique and ordered")
        available = set(stream_ids)
        for artifact in self.derived_artifacts:
            missing = set(artifact.derived_from_stream_ids) - available
            if missing:
                raise ValueError(f"derived evidence artifact references missing streams: {sorted(missing)}")

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class EvidenceBundleReceipt:
    bundle_id: str
    run_id: str
    manifest_ref: str
    manifest_sha256: str


__all__ = [
    "DerivedEvidenceArtifact",
    "EvidenceBundleManifest",
    "EvidenceBundleReceipt",
    "EvidenceBundleStatus",
    "EvidenceStreamDescriptor",
]
