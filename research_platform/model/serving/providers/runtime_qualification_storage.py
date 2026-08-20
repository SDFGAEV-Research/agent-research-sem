from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes

from ..api.runtime_qualification import RuntimeQualificationReceipt


class DirectoryRuntimeQualificationEvidenceStore:
    """Directory backend for immutable runtime-qualification receipts."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, runtime_manifest_digest: str, deployment_id: str) -> Path:
        safe = deployment_id.replace("/", "_")
        return self.root / runtime_manifest_digest / f"{safe}.json"

    def publish(self, runtime_manifest_digest: str, receipt: RuntimeQualificationReceipt) -> str:
        if not runtime_manifest_digest:
            raise ValueError("runtime manifest digest required")
        path = self._path(runtime_manifest_digest, receipt.deployment_id)
        payload = {"receipt": asdict(receipt), "receipt_digest": receipt.digest()}
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise RuntimeError("runtime qualification receipt already exists with different evidence")
            return str(path)
        atomic_replace_bytes(path, raw)
        return str(path)

    def load(self, runtime_manifest_digest: str, deployment_id: str) -> RuntimeQualificationReceipt:
        path = self._path(runtime_manifest_digest, deployment_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        receipt = RuntimeQualificationReceipt(
            **{
                **payload["receipt"],
                "qualified_roles": tuple(payload["receipt"]["qualified_roles"]),
                "evidence_refs": tuple(payload["receipt"]["evidence_refs"]),
            }
        )
        if receipt.digest() != payload.get("receipt_digest"):
            raise RuntimeError("runtime qualification evidence digest mismatch")
        return receipt


__all__ = ["DirectoryRuntimeQualificationEvidenceStore"]
