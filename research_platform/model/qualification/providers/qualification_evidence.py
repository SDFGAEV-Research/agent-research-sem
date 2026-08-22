"""Durable, checksummed storage for deployment-qualification evidence."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from research_platform.platform.kernel import canonical_bytes
from research_platform.platform.kernel.durability import (
    ChecksummedDocumentError,
    atomic_replace_bytes,
    decode_checksummed_document,
    encode_checksummed_document,
)
from research_platform.model.qualification.api import (
    BackendCandidatePlan,
    CandidateDecision,
    CudaFacts,
    DeploymentCapabilityFacts,
    DeploymentQualificationEvidenceRecord,
    DeploymentQualificationEvidenceStorePort,
    DeploymentQualificationPlan,
    DeploymentQualificationRequest,
    GpuCapabilityFacts,
    InstallPackage,
    ModelArtifactFacts,
    OperatingSystemFacts,
    PackageIndexFacts,
    PythonRuntimeFacts,
)


_SCHEMA = "model-deployment-qualification-evidence.v1"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class QualificationEvidenceIntegrityError(RuntimeError):
    """Raised when a persisted qualification record is malformed or altered."""


class FileDeploymentQualificationEvidenceStore(DeploymentQualificationEvidenceStorePort):
    """Publish one immutable qualification record per plan digest."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def publish(self, record: DeploymentQualificationEvidenceRecord) -> DeploymentQualificationEvidenceRecord:
        atomic_replace_bytes(
            self._path(record.plan.plan_digest),
            encode_checksummed_document(_SCHEMA, self._payload(record)),
        )
        return record

    def get(self, plan_digest: str) -> DeploymentQualificationEvidenceRecord:
        if _DIGEST_RE.fullmatch(plan_digest) is None:
            raise ValueError("qualification plan digest must be a lowercase SHA-256 digest")
        path = self._path(plan_digest)
        if not path.is_file():
            raise KeyError(plan_digest)
        try:
            document = decode_checksummed_document(path.read_bytes(), expected_schema=_SCHEMA)
            record = self._record(document.payload)
        except (ChecksummedDocumentError, KeyError, TypeError, ValueError, OSError) as exc:
            raise QualificationEvidenceIntegrityError(
                f"invalid qualification evidence record: {plan_digest}"
            ) from exc
        if record.plan.plan_digest != plan_digest:
            raise QualificationEvidenceIntegrityError(
                f"qualification evidence plan digest mismatch: {plan_digest}"
            )
        return record

    def _path(self, plan_digest: str) -> Path:
        return self._root / f"{plan_digest}.json"

    @staticmethod
    def _payload(record: DeploymentQualificationEvidenceRecord) -> dict[str, Any]:
        return json.loads(canonical_bytes(record).decode("utf-8"))

    @staticmethod
    def _record(payload: dict[str, Any]) -> DeploymentQualificationEvidenceRecord:
        request_data = dict(payload["request"])
        request = DeploymentQualificationRequest(
            model_id=str(request_data["model_id"]),
            model_path=Path(str(request_data["model_path"])),
            python_executable=Path(str(request_data["python_executable"])),
            backends=tuple(str(item) for item in request_data.get("backends", ())),
            tensor_parallel=int(request_data.get("tensor_parallel", 1)),
            package_index_urls=tuple(str(item) for item in request_data.get("package_index_urls", ())),
            probe_timeout_seconds=float(request_data.get("probe_timeout_seconds", 30.0)),
        )

        facts_data = dict(payload["facts"])
        os_data = dict(facts_data["operating_system"])
        cuda_data = dict(facts_data["cuda"])
        python_data = dict(facts_data["python"])
        model_data = dict(facts_data["model"])
        facts = DeploymentCapabilityFacts(
            captured_at_unix=float(facts_data["captured_at_unix"]),
            operating_system=OperatingSystemFacts(
                system=str(os_data["system"]),
                distribution=str(os_data["distribution"]),
                distribution_version=str(os_data["distribution_version"]),
                kernel=str(os_data["kernel"]),
                machine=str(os_data["machine"]),
            ),
            cuda=CudaFacts(
                driver_version=str(cuda_data["driver_version"]) if cuda_data.get("driver_version") else None,
                driver_cuda_version=str(cuda_data["driver_cuda_version"])
                if cuda_data.get("driver_cuda_version")
                else None,
                toolkit_version=str(cuda_data["toolkit_version"]) if cuda_data.get("toolkit_version") else None,
                nvrtc_versions=tuple(str(item) for item in cuda_data.get("nvrtc_versions", ())),
                evidence=tuple(str(item) for item in cuda_data.get("evidence", ())),
            ),
            gpus=tuple(
                GpuCapabilityFacts(
                    index=str(item["index"]),
                    uuid=str(item["uuid"]),
                    name=str(item["name"]),
                    total_memory_mb=int(item["total_memory_mb"]),
                    free_memory_mb=int(item["free_memory_mb"]),
                    compute_capability=str(item["compute_capability"])
                    if item.get("compute_capability")
                    else None,
                )
                for item in facts_data.get("gpus", ())
            ),
            python=PythonRuntimeFacts(
                executable=str(python_data["executable"]),
                version=str(python_data["version"]),
                pip_version=str(python_data["pip_version"]) if python_data.get("pip_version") else None,
                ensurepip_available=bool(python_data["ensurepip_available"]),
                venv_available=bool(python_data["venv_available"]),
                site_packages=str(python_data["site_packages"]) if python_data.get("site_packages") else None,
                torch_version=str(python_data["torch_version"]) if python_data.get("torch_version") else None,
                torch_cuda_version=str(python_data["torch_cuda_version"])
                if python_data.get("torch_cuda_version")
                else None,
                kernel_architectures=tuple(str(item) for item in python_data.get("kernel_architectures", ())),
                errors=tuple(str(item) for item in python_data.get("errors", ())),
            ),
            model=ModelArtifactFacts(
                model_id=str(model_data["model_id"]),
                model_path=str(model_data["model_path"]),
                model_type=str(model_data["model_type"]) if model_data.get("model_type") else None,
                architectures=tuple(str(item) for item in model_data.get("architectures", ())),
                torch_dtype=str(model_data["torch_dtype"]) if model_data.get("torch_dtype") else None,
                context_length=int(model_data["context_length"]) if model_data.get("context_length") else None,
                config_present=bool(model_data["config_present"]),
                error=str(model_data["error"]) if model_data.get("error") else None,
            ),
            package_indexes=tuple(
                PackageIndexFacts(
                    package=str(item["package"]),
                    index_url=str(item["index_url"]),
                    available_versions=tuple(str(version) for version in item.get("available_versions", ())),
                    error=str(item["error"]) if item.get("error") else None,
                )
                for item in facts_data.get("package_indexes", ())
            ),
            probe_errors=tuple(str(item) for item in facts_data.get("probe_errors", ())),
        )

        plan_data = dict(payload["plan"])
        plan = DeploymentQualificationPlan(
            request_digest=str(plan_data["request_digest"]),
            facts_digest=str(plan_data["facts_digest"]),
            candidates=tuple(
                BackendCandidatePlan(
                    backend=str(candidate["backend"]),
                    decision=CandidateDecision(str(candidate["decision"])),
                    version=str(candidate["version"]) if candidate.get("version") else None,
                    packages=tuple(
                        InstallPackage(
                            name=str(package["name"]),
                            version=str(package["version"]),
                            index_url=str(package["index_url"]),
                        )
                        for package in candidate.get("packages", ())
                    ),
                    reasons=tuple(str(reason) for reason in candidate.get("reasons", ())),
                    evidence_refs=tuple(str(ref) for ref in candidate.get("evidence_refs", ())),
                )
                for candidate in plan_data.get("candidates", ())
            ),
            selected_backend=str(plan_data["selected_backend"])
            if plan_data.get("selected_backend")
            else None,
        )
        if plan.plan_digest != str(plan_data.get("plan_digest", "")):
            raise QualificationEvidenceIntegrityError("qualification plan digest mismatch")
        record = DeploymentQualificationEvidenceRecord(
            captured_at_unix=float(payload["captured_at_unix"]),
            request=request,
            facts=facts,
            plan=plan,
        )
        if record.record_digest != str(payload.get("record_digest", "")):
            raise QualificationEvidenceIntegrityError("qualification record digest mismatch")
        return record


__all__ = [
    "FileDeploymentQualificationEvidenceStore",
    "QualificationEvidenceIntegrityError",
]
