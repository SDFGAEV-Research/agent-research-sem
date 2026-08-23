from __future__ import annotations

import json

from research_platform.platform.kernel import canonical_bytes

from ..api import (
    WorkloadCheckpointComponentRef,
    WorkloadCheckpointManifest,
    WorkloadExecutionCut,
)


class WorkloadCheckpointManifestCodec:
    """Pure codec for the workload checkpoint manifest document."""

    @staticmethod
    def encode(manifest: WorkloadCheckpointManifest) -> bytes:
        return canonical_bytes({"manifest": manifest, "manifest_digest": manifest.digest()})

    @staticmethod
    def decode(payload: bytes) -> WorkloadCheckpointManifest:
        try:
            document = json.loads(payload)
            raw = dict(document["manifest"])
            raw["execution_cut"] = WorkloadExecutionCut(**dict(raw["execution_cut"]))
            raw["component_refs"] = tuple(
                WorkloadCheckpointComponentRef(**dict(item))
                for item in raw.get("component_refs", ())
            )
            manifest = WorkloadCheckpointManifest(**raw)
            expected = str(document["manifest_digest"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            from ..api import RunCheckpointIntegrityError

            raise RunCheckpointIntegrityError("invalid workload checkpoint manifest document") from exc
        if manifest.digest() != expected:
            from ..api import RunCheckpointIntegrityError

            raise RunCheckpointIntegrityError("workload checkpoint manifest digest mismatch")
        return manifest


__all__ = ["WorkloadCheckpointManifestCodec"]
