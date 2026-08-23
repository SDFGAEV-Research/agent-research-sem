from __future__ import annotations

import json
import hashlib
from pathlib import Path

from research_platform.experimentation.run.api import RunArtifactKind, RunArtifactStorePort
from research_platform.platform.kernel import canonical_bytes

from ..api import (
    DerivedEvidenceArtifact,
    EvidenceBundleManifest,
    EvidenceBundleReceipt,
    EvidenceBundleStatus,
    EvidenceStreamDescriptor,
)


class EvidenceBundleDecodeError(ValueError):
    pass


def encode_evidence_bundle_manifest(manifest: EvidenceBundleManifest) -> bytes:
    return canonical_bytes(manifest, indent=2) + b"\n"


def decode_evidence_bundle_manifest(raw: bytes) -> EvidenceBundleManifest:
    try:
        document = json.loads(raw.decode("utf-8"))
        fields = {
            "schema_version",
            "bundle_id",
            "run_id",
            "status",
            "source_checkpoint_id",
            "streams",
            "derived_artifacts",
        }
        if not isinstance(document, dict) or set(document) != fields:
            raise TypeError("evidence bundle fields are not exact")
        for field in ("schema_version", "bundle_id", "run_id", "status"):
            if not isinstance(document[field], str):
                raise TypeError(f"evidence bundle {field} must be a string")
        streams_raw = document["streams"]
        artifacts_raw = document["derived_artifacts"]
        if not isinstance(streams_raw, list) or not isinstance(artifacts_raw, list):
            raise TypeError("evidence bundle collections must be lists")

        stream_fields = {
            "stream_id",
            "family",
            "schema_version",
            "artifact_ref",
            "record_count",
            "content_sha256",
            "required",
            "source_of_truth",
        }
        streams: list[EvidenceStreamDescriptor] = []
        for row in streams_raw:
            if not isinstance(row, dict) or set(row) != stream_fields:
                raise TypeError("evidence stream fields are not exact")
            for field in (
                "stream_id",
                "family",
                "schema_version",
                "artifact_ref",
                "content_sha256",
            ):
                if not isinstance(row[field], str):
                    raise TypeError(f"evidence stream {field} must be a string")
            if type(row["record_count"]) is not int:
                raise TypeError("evidence stream record_count must be an integer")
            if type(row["required"]) is not bool or type(row["source_of_truth"]) is not bool:
                raise TypeError("evidence stream flags must be booleans")
            streams.append(EvidenceStreamDescriptor(**row))

        artifact_fields = {
            "artifact_id",
            "artifact_kind",
            "artifact_ref",
            "content_sha256",
            "derived_from_stream_ids",
        }
        artifacts: list[DerivedEvidenceArtifact] = []
        for row in artifacts_raw:
            if not isinstance(row, dict) or set(row) != artifact_fields:
                raise TypeError("derived evidence artifact fields are not exact")
            for field in ("artifact_id", "artifact_kind", "artifact_ref", "content_sha256"):
                if not isinstance(row[field], str):
                    raise TypeError(f"derived evidence artifact {field} must be a string")
            source_ids = row["derived_from_stream_ids"]
            if not isinstance(source_ids, list) or any(
                not isinstance(item, str) for item in source_ids
            ):
                raise TypeError("derived evidence source ids must be strings")
            artifacts.append(
                DerivedEvidenceArtifact(
                    artifact_id=row["artifact_id"],
                    artifact_kind=row["artifact_kind"],
                    artifact_ref=row["artifact_ref"],
                    content_sha256=row["content_sha256"],
                    derived_from_stream_ids=tuple(source_ids),
                )
            )
        checkpoint = document["source_checkpoint_id"]
        if checkpoint is not None and not isinstance(checkpoint, str):
            raise TypeError("evidence bundle source_checkpoint_id must be a string or null")
        return EvidenceBundleManifest(
            schema_version=document["schema_version"],
            bundle_id=document["bundle_id"],
            run_id=document["run_id"],
            status=EvidenceBundleStatus(document["status"]),
            source_checkpoint_id=checkpoint,
            streams=tuple(streams),
            derived_artifacts=tuple(artifacts),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise EvidenceBundleDecodeError("evidence bundle violates the frozen manifest contract") from exc


def load_evidence_bundle_manifest(path: str | Path) -> EvidenceBundleManifest:
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise EvidenceBundleDecodeError(f"evidence bundle manifest is not a regular file: {target}")
    try:
        return decode_evidence_bundle_manifest(target.read_bytes())
    except OSError as exc:
        raise EvidenceBundleDecodeError("evidence bundle manifest cannot be read") from exc


class RunArtifactEvidenceBundlePublisher:
    """Publish one validated final manifest through the run artifact authority."""

    def __init__(self, artifacts: RunArtifactStorePort) -> None:
        self._artifacts = artifacts

    def publish(self, manifest: EvidenceBundleManifest) -> EvidenceBundleReceipt:
        encoded = canonical_bytes(manifest)
        manifest_ref = self._artifacts.publish_text(
            f"evidence/{manifest.bundle_id}/manifest.json",
            encoded.decode("utf-8"),
            kind=RunArtifactKind.EVIDENCE,
        )
        return EvidenceBundleReceipt(
            manifest.bundle_id,
            manifest.run_id,
            manifest_ref,
            hashlib.sha256(encoded).hexdigest(),
        )


__all__ = [
    "EvidenceBundleDecodeError",
    "RunArtifactEvidenceBundlePublisher",
    "decode_evidence_bundle_manifest",
    "encode_evidence_bundle_manifest",
    "load_evidence_bundle_manifest",
]
