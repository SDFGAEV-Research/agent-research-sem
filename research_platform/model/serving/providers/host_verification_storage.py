from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes

from ..api.host_verification import HostInventoryReceipt, HostResourceDelta


class DirectoryHostInventoryEvidenceStore:
    """Filesystem backend for host inventory and resource-delta evidence."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, runtime_manifest_digest: str, phase: str) -> Path:
        return self.root / f"{runtime_manifest_digest}.{phase}.host-inventory.json"

    def publish(self, runtime_manifest_digest: str, receipt: HostInventoryReceipt) -> str:
        path = self._path(runtime_manifest_digest, receipt.phase)
        atomic_replace_bytes(
            path,
            json.dumps(asdict(receipt), sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        return str(path)

    def load(self, runtime_manifest_digest: str, phase: str) -> HostInventoryReceipt:
        path = self._path(runtime_manifest_digest, phase)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["gpu_free_memory_bytes"] = tuple(tuple(item) for item in data["gpu_free_memory_bytes"])
        data["listening_ports"] = tuple(data["listening_ports"])
        data["mount_free_bytes"] = tuple(tuple(item) for item in data["mount_free_bytes"])
        receipt = HostInventoryReceipt(**data)
        base = {key: value for key, value in asdict(receipt).items() if key != "receipt_digest"}
        raw = json.dumps(base, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != receipt.receipt_digest:
            raise ValueError("host inventory receipt digest mismatch")
        return receipt

    def publish_delta(self, runtime_manifest_digest: str, delta: HostResourceDelta) -> str:
        path = self.root / (
            f"{runtime_manifest_digest}.{delta.before_phase}-to-{delta.after_phase}.host-delta.json"
        )
        atomic_replace_bytes(
            path,
            json.dumps(asdict(delta), sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        return str(path)


__all__ = ["DirectoryHostInventoryEvidenceStore"]
