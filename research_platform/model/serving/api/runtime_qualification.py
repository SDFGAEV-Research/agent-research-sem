from __future__ import annotations

from dataclasses import dataclass
import time

from research_platform.platform.kernel import canonical_digest
from .heartbeat import ServiceHeartbeat
from .qualified_deployment import QualifiedDeploymentManifest


@dataclass(frozen=True, slots=True)
class RuntimeQualificationReceipt:
    """Immutable proof that a live deployment still satisfies its frozen qualification."""

    deployment_id: str
    stack_digest: str
    qualification_certificate_digest: str
    heartbeat_qualification_digest: str
    qualified_roles: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    created_at: float

    def digest(self) -> str:
        return canonical_digest(self)


def build_runtime_qualification_receipt(
    deployment: QualifiedDeploymentManifest,
    heartbeat: ServiceHeartbeat,
    *,
    required_roles: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    max_heartbeat_age_seconds: float,
    now: float | None = None,
) -> RuntimeQualificationReceipt:
    """Validate live qualification against one exact frozen deployment.

    This module owns only qualification semantics.  Durable publication is an
    independent backend concern exposed through ``RuntimeQualificationEvidenceStorePort``.
    """

    if heartbeat.deployment_id != deployment.deployment_id:
        raise ValueError("runtime qualification heartbeat belongs to another deployment")
    if heartbeat.stack_digest != deployment.stack.digest():
        raise ValueError("runtime qualification stack digest drift")
    if not heartbeat.ready:
        raise ValueError("runtime qualification requires READY service")
    if heartbeat.age(now) > max_heartbeat_age_seconds:
        raise ValueError("runtime qualification heartbeat is stale")

    certificate_digest = deployment.certificate.digest()
    if heartbeat.qualification_digest != certificate_digest:
        raise ValueError("live service qualification digest does not match frozen certificate")

    allowed = set(deployment.certificate.qualified_roles)
    missing = set(required_roles) - allowed
    if missing:
        raise ValueError(f"runtime qualification certificate missing roles: {sorted(missing)}")
    if not evidence_refs:
        raise ValueError("runtime qualification requires concrete evidence refs")

    return RuntimeQualificationReceipt(
        deployment_id=deployment.deployment_id,
        stack_digest=deployment.stack.digest(),
        qualification_certificate_digest=certificate_digest,
        heartbeat_qualification_digest=heartbeat.qualification_digest,
        qualified_roles=tuple(sorted(required_roles)),
        evidence_refs=tuple(evidence_refs),
        created_at=time.time() if now is None else now,
    )


__all__ = ["RuntimeQualificationReceipt", "build_runtime_qualification_receipt"]
