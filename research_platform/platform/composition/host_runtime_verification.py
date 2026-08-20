from __future__ import annotations

from research_platform.model.serving.api.host_verification import (
    build_host_inventory_receipt,
    compare_host_inventory_receipts,
)
from research_platform.model.serving.api.host_verification_ports import (
    HostInventoryEvidenceStorePort,
    HostInventoryProvider,
)
from research_platform.execution.runtime.manager.contracts import FrozenRuntimeManifest


class HostInventoryRuntimeVerification:
    """Model/host-OS adapter implementing Runtime Manager's narrow host port."""

    def __init__(
        self,
        provider: HostInventoryProvider,
        evidence_store: HostInventoryEvidenceStorePort,
    ) -> None:
        self._provider = provider
        self._evidence_store = evidence_store

    def verify_pre_start(self, manifest: FrozenRuntimeManifest) -> tuple[str, ...]:
        inventory = self._provider.capture()
        receipt = build_host_inventory_receipt(
            manifest.target_host_identity_digest,
            inventory,
            phase="pre_start",
        )
        ref = self._evidence_store.publish(manifest.digest(), receipt)
        return (
            ref,
            f"host-identity:{receipt.host_identity_digest}",
            f"host-snapshot:{receipt.snapshot_digest}",
        )

    def verify_post_ready(self, manifest: FrozenRuntimeManifest) -> tuple[str, ...]:
        inventory = self._provider.capture()
        post = build_host_inventory_receipt(
            manifest.target_host_identity_digest,
            inventory,
            phase="post_ready",
        )
        manifest_digest = manifest.digest()
        post_ref = self._evidence_store.publish(manifest_digest, post)
        pre = self._evidence_store.load(manifest_digest, "pre_start")
        delta = compare_host_inventory_receipts(pre, post)
        delta_ref = self._evidence_store.publish_delta(manifest_digest, delta)
        return (
            post_ref,
            delta_ref,
            f"host-post-snapshot:{post.snapshot_digest}",
            f"host-resource-delta:{delta.delta_digest}",
        )


__all__ = ["HostInventoryRuntimeVerification"]
