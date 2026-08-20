from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import canonical_digest


@dataclass(frozen=True, slots=True)
class ServiceLaunchContract:
    service_id: str
    generation: str
    executable: str
    argv: tuple[str, ...]
    cwd: str
    environment_digest: str
    artifact_digest: str
    runtime_identity_digest: str
    readiness_timeout_s: float
    stop_timeout_s: float
    heartbeat_interval_s: float

    def __post_init__(self) -> None:
        if not self.service_id or not self.generation:
            raise ValueError("service identity required")
        if not self.executable.startswith("/"):
            raise ValueError("service executable must be an absolute path")
        if not self.argv or self.argv[0] != self.executable:
            raise ValueError("argv[0] must equal frozen executable")
        if not self.cwd.startswith("/"):
            raise ValueError("service cwd must be an absolute path")
        if min(self.readiness_timeout_s, self.stop_timeout_s, self.heartbeat_interval_s) <= 0:
            raise ValueError("service timeouts/heartbeat must be positive")
        for digest in (self.environment_digest, self.artifact_digest, self.runtime_identity_digest):
            if len(digest) != 64:
                raise ValueError("service contract digests must be SHA-256 hex")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ServiceProcessIdentity:
    pid: int
    start_identity: str
    process_group_id: int | None = None


class ServiceContractDrift(RuntimeError):
    """Observed service runtime identity does not match the frozen launch contract."""


__all__ = ["ServiceContractDrift", "ServiceLaunchContract", "ServiceProcessIdentity"]
