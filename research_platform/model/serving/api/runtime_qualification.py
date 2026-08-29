from __future__ import annotations

from dataclasses import dataclass
import math
import time

from research_platform.platform.kernel import canonical_digest
from .heartbeat import ServiceHeartbeat
from .qualified_deployment import QualifiedDeploymentManifest


def _require_digest(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


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
    def __post_init__(self) -> None:
        if not isinstance(self.deployment_id, str) or not self.deployment_id.strip():
            raise ValueError("runtime qualification deployment_id is required")
        _require_digest(self.stack_digest, "stack_digest")
        _require_digest(
            self.qualification_certificate_digest,
            "qualification_certificate_digest",
        )
        _require_digest(
            self.heartbeat_qualification_digest,
            "heartbeat_qualification_digest",
        )
        if self.heartbeat_qualification_digest != self.qualification_certificate_digest:
            raise ValueError("runtime qualification heartbeat/certificate digest drift")
        if not isinstance(self.qualified_roles, tuple) or not self.qualified_roles:
            raise TypeError("runtime qualification roles must be a non-empty tuple")
        if any(type(role) is not str or not role.strip() for role in self.qualified_roles):
            raise TypeError("runtime qualification roles must be non-empty strings")
        if len(set(self.qualified_roles)) != len(self.qualified_roles):
            raise ValueError("runtime qualification roles must be unique")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise TypeError("runtime qualification evidence refs must be a non-empty tuple")
        if any(type(ref) is not str or not ref.strip() for ref in self.evidence_refs):
            raise TypeError("runtime qualification evidence refs must be non-empty strings")
        if type(self.created_at) is not float or not math.isfinite(self.created_at) or self.created_at < 0:
            raise TypeError("runtime qualification created_at must be a finite non-negative float")

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
    """Validate live qualification against one exact frozen deployment."""

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

    created_at = time.time() if now is None else now
    if type(created_at) is not float:
        created_at = float(created_at)
    return RuntimeQualificationReceipt(
        deployment_id=deployment.deployment_id,
        stack_digest=deployment.stack.digest(),
        qualification_certificate_digest=certificate_digest,
        heartbeat_qualification_digest=heartbeat.qualification_digest,
        qualified_roles=tuple(sorted(required_roles)),
        evidence_refs=tuple(evidence_refs),
        created_at=created_at,
    )


__all__ = ["RuntimeQualificationReceipt", "build_runtime_qualification_receipt"]
