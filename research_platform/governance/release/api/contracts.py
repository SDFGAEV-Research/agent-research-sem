from __future__ import annotations

from dataclasses import dataclass
import time

from research_platform.platform.kernel import canonical_digest


class ActiveReleasePinned(RuntimeError):
    """A release lifecycle mutation conflicts with an authoritative active pin."""


@dataclass(frozen=True, slots=True)
class ActiveReleasePin:
    control_id: str
    runtime_manifest_digest: str
    release_digest: str
    acquired_at: float

    def __post_init__(self) -> None:
        if not self.control_id:
            raise ValueError("release pin control_id required")
        for value in (self.runtime_manifest_digest, self.release_digest):
            if len(value) != 64:
                raise ValueError("release pin digests must be SHA-256")
        if self.acquired_at <= 0:
            raise ValueError("release pin acquisition timestamp required")

    @classmethod
    def create(cls, control_id: str, runtime_manifest_digest: str, release_digest: str) -> "ActiveReleasePin":
        return cls(control_id, runtime_manifest_digest, release_digest, time.time())


@dataclass(frozen=True, slots=True)
class ReleaseConsumerQuiescence:
    consumer_id: str
    quiescent: bool
    summary: str
    evidence_refs: tuple[str, ...] = ()



@dataclass(frozen=True, slots=True)
class ReleaseQuiescenceProof:
    control_id: str
    runtime_manifest_digest: str
    release_digest: str
    observed_at: float
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    @classmethod
    def create(
        cls,
        pin: ActiveReleasePin,
        *,
        blockers: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> "ReleaseQuiescenceProof":
        return cls(
            pin.control_id,
            pin.runtime_manifest_digest,
            pin.release_digest,
            time.time(),
            blockers,
            evidence_refs,
        )

    @property
    def quiescent(self) -> bool:
        return not self.blockers

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class FileDigest:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    schema_version: int
    files: tuple[FileDigest, ...]
    source_tree_sha256: str
    python_requires: str
    platform_code_version: str

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ReleaseQualityEvidence:
    architecture_report_sha256: str
    architecture_clean: bool
    no_degradation_findings: int
    silent_failure_findings: int

    @property
    def clean(self) -> bool:
        return (
            self.architecture_clean
            and self.no_degradation_findings == 0
            and self.silent_failure_findings == 0
        )

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class RunLaunchManifest:
    release_digest: str
    prompt_generation_digest: str
    role_model_manifest_digest: str
    participant_implementation_inventory_digest: str
    participant_runtime_inventory_digest: str
    participant_binding_manifest_digest: str
    experiment_spec_digest: str
    host_fingerprint: str
    command_argv: tuple[str, ...]
    config_digests: tuple[tuple[str, str], ...]
    seed_identity: str
    prompt_promotion_digest: str = ""

    def __post_init__(self) -> None:
        if not self.participant_implementation_inventory_digest.strip():
            raise ValueError("run launch manifest requires implementation inventory digest")
        if not self.participant_runtime_inventory_digest.strip():
            raise ValueError("run launch manifest requires participant runtime inventory digest")
        if not self.participant_binding_manifest_digest.strip():
            raise ValueError("run launch manifest requires participant binding manifest digest")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ReleaseVerificationReport:
    clean: bool
    manifest_digest: str
    source_tree_sha256: str
    file_count: int
    errors: tuple[str, ...]


class ReleaseVerificationIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseVerificationEvidence:
    release_manifest_digest: str
    source_tree_sha256: str
    platform_code_version: str


__all__ = [
    "ActiveReleasePin",
    "ActiveReleasePinned",
    "FileDigest",
    "ReleaseConsumerQuiescence",
    "ReleaseManifest",
    "ReleaseQuiescenceProof",
    "ReleaseVerificationEvidence",
    "ReleaseVerificationReport",
    "ReleaseVerificationIntegrityError",
    "RunLaunchManifest",
]
