from __future__ import annotations

from dataclasses import dataclass

from research_platform.model.serving.api import (
    QualifiedDeploymentManifest,
    RoleModelManifest,
    RuntimeQualificationReceipt,
)

from .contracts import ModelEndpointRoute


def _require_digest(value: str, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class QualifiedModelClosurePublication:
    role_manifest: RoleModelManifest
    deployments: tuple[QualifiedDeploymentManifest, ...]
    routes: tuple[ModelEndpointRoute, ...]
    runtime_manifest_digest: str
    runtime_qualification_receipts: tuple[RuntimeQualificationReceipt, ...]
    runtime_qualification_root: str = "qualification"

    def __post_init__(self) -> None:
        if type(self.deployments) is not tuple or not self.deployments:
            raise TypeError("qualified closure publication deployments must be a non-empty tuple")
        if type(self.routes) is not tuple or not self.routes:
            raise TypeError("qualified closure publication routes must be a non-empty tuple")
        if type(self.runtime_qualification_receipts) is not tuple or not self.runtime_qualification_receipts:
            raise TypeError(
                "qualified closure publication runtime receipts must be a non-empty tuple"
            )
        _require_digest(self.runtime_manifest_digest, "runtime_manifest_digest")
        if type(self.runtime_qualification_root) is not str or not self.runtime_qualification_root.strip():
            raise TypeError("qualified closure publication runtime qualification root is required")


@dataclass(frozen=True, slots=True)
class QualifiedModelClosurePublicationReceipt:
    closure_path: str
    closure_digest: str
    runtime_evidence_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.closure_path) is not str or not self.closure_path.strip():
            raise ValueError("qualified closure publication receipt requires a path")
        _require_digest(self.closure_digest, "closure_digest")
        if type(self.runtime_evidence_paths) is not tuple or not self.runtime_evidence_paths:
            raise TypeError("qualified closure publication receipt requires runtime evidence paths")
        if any(type(path) is not str or not path.strip() for path in self.runtime_evidence_paths):
            raise TypeError("qualified closure runtime evidence paths must be non-empty strings")


__all__ = [
    "QualifiedModelClosurePublication",
    "QualifiedModelClosurePublicationReceipt",
]
