from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from .inventory import HostInventory


def _digest(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class HostInventoryReceipt:
    schema_version: int
    phase: str
    host_identity_digest: str
    snapshot_digest: str
    captured_at_unix: float
    effective_available_memory_bytes: int
    gpu_free_memory_bytes: tuple[tuple[str, int], ...]
    listening_ports: tuple[int, ...]
    mount_free_bytes: tuple[tuple[str, int], ...]
    runtime: dict[str, object]
    receipt_digest: str


@dataclass(frozen=True, slots=True)
class HostResourceDelta:
    schema_version: int
    before_phase: str
    after_phase: str
    before_snapshot_digest: str
    after_snapshot_digest: str
    host_memory_delta_bytes: int
    gpu_free_memory_delta_bytes: tuple[tuple[str, int], ...]
    ports_added: tuple[int, ...]
    ports_removed: tuple[int, ...]
    mount_free_delta_bytes: tuple[tuple[str, int], ...]
    delta_digest: str


def _receipt_base(inventory: HostInventory, phase: str) -> dict[str, object]:
    if not phase or any(ch.isspace() for ch in phase):
        raise ValueError("host inventory phase must be a stable token")
    return {
        "schema_version": 1,
        "phase": phase,
        "host_identity_digest": inventory.identity_digest(),
        "snapshot_digest": inventory.snapshot_digest(),
        "captured_at_unix": inventory.captured_at_unix,
        "effective_available_memory_bytes": inventory.memory.effective_available_bytes,
        "gpu_free_memory_bytes": tuple((gpu.uuid, gpu.free_memory_bytes) for gpu in inventory.gpus),
        "listening_ports": inventory.listening_ports,
        "mount_free_bytes": tuple((mount.path, mount.free_bytes) for mount in inventory.mounts),
        "runtime": asdict(inventory.runtime),
    }


def build_host_inventory_receipt(
    expected_host_identity_digest: str,
    inventory: HostInventory,
    *,
    phase: str,
) -> HostInventoryReceipt:
    base = _receipt_base(inventory, phase)
    if base["host_identity_digest"] != expected_host_identity_digest:
        raise ValueError("live host/runtime identity differs from run launch manifest")
    digest = _digest(base)
    return HostInventoryReceipt(
        1,
        phase,
        str(base["host_identity_digest"]),
        str(base["snapshot_digest"]),
        float(base["captured_at_unix"]),
        int(base["effective_available_memory_bytes"]),
        tuple(base["gpu_free_memory_bytes"]),  # type: ignore[arg-type]
        tuple(base["listening_ports"]),  # type: ignore[arg-type]
        tuple(base["mount_free_bytes"]),  # type: ignore[arg-type]
        dict(base["runtime"]),  # type: ignore[arg-type]
        digest,
    )


def compare_host_inventory_receipts(
    before: HostInventoryReceipt,
    after: HostInventoryReceipt,
) -> HostResourceDelta:
    if before.host_identity_digest != after.host_identity_digest:
        raise ValueError("cannot compare host resource snapshots from different host identities")
    before_gpus = dict(before.gpu_free_memory_bytes)
    after_gpus = dict(after.gpu_free_memory_bytes)
    if set(before_gpus) != set(after_gpus):
        raise ValueError("GPU identity set changed between host resource snapshots")
    before_mounts = dict(before.mount_free_bytes)
    after_mounts = dict(after.mount_free_bytes)
    if set(before_mounts) != set(after_mounts):
        raise ValueError("mount identity set changed between host resource snapshots")

    base = {
        "schema_version": 1,
        "before_phase": before.phase,
        "after_phase": after.phase,
        "before_snapshot_digest": before.snapshot_digest,
        "after_snapshot_digest": after.snapshot_digest,
        "host_memory_delta_bytes": after.effective_available_memory_bytes - before.effective_available_memory_bytes,
        "gpu_free_memory_delta_bytes": tuple(
            (key, after_gpus[key] - before_gpus[key]) for key in sorted(before_gpus)
        ),
        "ports_added": tuple(sorted(set(after.listening_ports) - set(before.listening_ports))),
        "ports_removed": tuple(sorted(set(before.listening_ports) - set(after.listening_ports))),
        "mount_free_delta_bytes": tuple(
            (key, after_mounts[key] - before_mounts[key]) for key in sorted(before_mounts)
        ),
    }
    return HostResourceDelta(
        1,
        str(base["before_phase"]),
        str(base["after_phase"]),
        str(base["before_snapshot_digest"]),
        str(base["after_snapshot_digest"]),
        int(base["host_memory_delta_bytes"]),
        tuple(base["gpu_free_memory_delta_bytes"]),  # type: ignore[arg-type]
        tuple(base["ports_added"]),  # type: ignore[arg-type]
        tuple(base["ports_removed"]),  # type: ignore[arg-type]
        tuple(base["mount_free_delta_bytes"]),  # type: ignore[arg-type]
        _digest(base),
    )


__all__ = [
    "HostInventoryReceipt",
    "HostResourceDelta",
    "build_host_inventory_receipt",
    "compare_host_inventory_receipts",
]
