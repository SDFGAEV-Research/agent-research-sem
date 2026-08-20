from __future__ import annotations

import json
from dataclasses import asdict

from research_platform.participant.core.api.checkpoint import ParticipantCheckpointRef

from ..api.contracts import RunCheckpointIntegrityError, RunCheckpointManifest, RunParticipantSnapshotRef


class RunCheckpointManifestCodec:
    """Pure document codec; owns no filesystem or checkpoint lifecycle authority."""

    @staticmethod
    def encode(manifest: RunCheckpointManifest) -> bytes:
        envelope = {
            "manifest": asdict(manifest),
            "manifest_digest": manifest.digest(),
        }
        return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def decode(payload: bytes) -> RunCheckpointManifest:
        try:
            envelope = json.loads(payload)
            raw_manifest = dict(envelope["manifest"])
            refs = []
            for row in raw_manifest.get("participant_snapshots", ()):
                row = dict(row)
                refs.append(
                    RunParticipantSnapshotRef(
                        checkpoint=ParticipantCheckpointRef(**dict(row["checkpoint"])),
                        generation=row.get("generation"),
                    )
                )
            raw_manifest["participant_snapshots"] = tuple(refs)
            manifest = RunCheckpointManifest(**raw_manifest)
            expected = str(envelope["manifest_digest"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RunCheckpointIntegrityError("invalid study checkpoint manifest document") from exc
        if manifest.digest() != expected:
            raise RunCheckpointIntegrityError("study checkpoint manifest digest mismatch")
        return manifest


__all__ = ["RunCheckpointManifestCodec"]
