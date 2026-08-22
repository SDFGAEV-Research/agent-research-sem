"""Composition-time deployment qualification contracts.

The contracts deliberately describe facts and a plan, not a mutable package
manager or a live model process.  Host facts are observations imported from
the resource/environment compositions; deployment owns the interpretation of
those facts for one exact model-serving request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from research_platform.platform.kernel import canonical_digest


class CandidateDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class OperatingSystemFacts:
    system: str
    distribution: str
    distribution_version: str
    kernel: str
    machine: str


@dataclass(frozen=True, slots=True)
class CudaFacts:
    driver_version: str | None
    driver_cuda_version: str | None
    toolkit_version: str | None
    nvrtc_versions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GpuCapabilityFacts:
    index: str
    uuid: str
    name: str
    total_memory_mb: int
    free_memory_mb: int
    compute_capability: str | None


@dataclass(frozen=True, slots=True)
class PythonRuntimeFacts:
    executable: str
    version: str
    pip_version: str | None
    ensurepip_available: bool
    venv_available: bool
    site_packages: str | None
    torch_version: str | None
    torch_cuda_version: str | None
    kernel_architectures: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelArtifactFacts:
    model_id: str
    model_path: str
    model_type: str | None
    architectures: tuple[str, ...]
    torch_dtype: str | None
    context_length: int | None
    config_present: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PackageIndexFacts:
    package: str
    index_url: str
    available_versions: tuple[str, ...] = ()
    error: str | None = None

    @property
    def latest(self) -> str | None:
        return self.available_versions[0] if self.available_versions else None


@dataclass(frozen=True, slots=True)
class DeploymentCapabilityFacts:
    captured_at_unix: float
    operating_system: OperatingSystemFacts
    cuda: CudaFacts
    gpus: tuple[GpuCapabilityFacts, ...]
    python: PythonRuntimeFacts
    model: ModelArtifactFacts
    package_indexes: tuple[PackageIndexFacts, ...]
    probe_errors: tuple[str, ...] = ()

    def digest(self) -> str:
        return canonical_digest(self)

    def package_index(self, package: str, index_url: str) -> PackageIndexFacts | None:
        for item in self.package_indexes:
            if item.package == package and item.index_url == index_url:
                return item
        return None


@dataclass(frozen=True, slots=True)
class DeploymentQualificationRequest:
    model_id: str
    model_path: Path
    python_executable: Path
    backends: tuple[str, ...] = ("sglang", "vllm")
    tensor_parallel: int = 1
    package_index_urls: tuple[str, ...] = ("https://pypi.org/simple",)
    probe_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("deployment qualification model_id is required")
        if self.tensor_parallel < 1:
            raise ValueError("deployment qualification tensor_parallel must be positive")
        if not self.backends or any(not value.strip() for value in self.backends):
            raise ValueError("deployment qualification requires at least one backend")
        if self.probe_timeout_seconds <= 0:
            raise ValueError("deployment qualification probe timeout must be positive")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class InstallPackage:
    name: str
    version: str
    index_url: str


@dataclass(frozen=True, slots=True)
class BackendCandidatePlan:
    backend: str
    decision: CandidateDecision
    version: str | None
    packages: tuple[InstallPackage, ...]
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeploymentQualificationPlan:
    request_digest: str
    facts_digest: str
    candidates: tuple[BackendCandidatePlan, ...]
    selected_backend: str | None
    plan_digest: str = field(init=False)

    def __post_init__(self) -> None:
        accepted = [item.backend for item in self.candidates if item.decision is CandidateDecision.ACCEPTED]
        if self.selected_backend is not None and self.selected_backend not in accepted:
            raise ValueError("selected backend must be an accepted candidate")
        object.__setattr__(
            self,
            "plan_digest",
            canonical_digest(
                {
                    "request_digest": self.request_digest,
                    "facts_digest": self.facts_digest,
                    "candidates": self.candidates,
                    "selected_backend": self.selected_backend,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class DeploymentQualificationEvidenceRecord:
    """Immutable join of one request, its captured facts and its plan."""

    captured_at_unix: float
    request: DeploymentQualificationRequest
    facts: DeploymentCapabilityFacts
    plan: DeploymentQualificationPlan
    record_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.plan.request_digest != self.request.digest():
            raise ValueError("qualification evidence request digest does not match plan")
        if self.plan.facts_digest != self.facts.digest():
            raise ValueError("qualification evidence facts digest does not match plan")
        object.__setattr__(
            self,
            "record_digest",
            canonical_digest(
                {
                    "captured_at_unix": self.captured_at_unix,
                    "request": self.request,
                    "facts": self.facts,
                    "plan": self.plan,
                }
            ),
        )


class DeploymentCapabilityProbePort(Protocol):
    def capture(self, request: DeploymentQualificationRequest) -> DeploymentCapabilityFacts: ...


class DeploymentQualificationPort(Protocol):
    def qualify(self, request: DeploymentQualificationRequest) -> DeploymentQualificationPlan: ...


class DeploymentQualificationEvidenceStorePort(Protocol):
    def publish(self, record: DeploymentQualificationEvidenceRecord) -> DeploymentQualificationEvidenceRecord: ...
    def get(self, plan_digest: str) -> DeploymentQualificationEvidenceRecord: ...


__all__ = [
    "BackendCandidatePlan",
    "CandidateDecision",
    "CudaFacts",
    "DeploymentCapabilityFacts",
    "DeploymentCapabilityProbePort",
    "DeploymentQualificationPlan",
    "DeploymentQualificationEvidenceRecord",
    "DeploymentQualificationEvidenceStorePort",
    "DeploymentQualificationPort",
    "DeploymentQualificationRequest",
    "GpuCapabilityFacts",
    "InstallPackage",
    "ModelArtifactFacts",
    "OperatingSystemFacts",
    "PackageIndexFacts",
    "PythonRuntimeFacts",
]
