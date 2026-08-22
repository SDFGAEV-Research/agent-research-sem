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
    GpuFabricFacts,
    HostExecutionFacts,
    InstallPackage,
    ModelArtifactFacts,
    OperatingSystemFacts,
    PackageArtifactFacts,
    PackageIndexFacts,
    PythonRuntimeFacts,
    StorageCapabilityFacts,
)


_SCHEMA = "model-deployment-qualification-evidence.v3"
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
        host_data = dict(facts_data.get("host", {}))
        fabric_data = dict(facts_data.get("fabric", {}))
        storage_data = dict(facts_data.get("storage", {}))
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
                nvml_version=str(cuda_data["nvml_version"]) if cuda_data.get("nvml_version") else None,
                runtime_library_versions=tuple(
                    str(item) for item in cuda_data.get("runtime_library_versions", ())
                ),
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
                    pci_bus_id=str(item["pci_bus_id"]) if item.get("pci_bus_id") else None,
                    numa_node=int(item["numa_node"]) if item.get("numa_node") is not None else None,
                    power_limit_watts=float(item["power_limit_watts"])
                    if item.get("power_limit_watts") is not None
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
                python_abi=str(python_data["python_abi"]) if python_data.get("python_abi") else None,
                platform_tag=str(python_data["platform_tag"]) if python_data.get("platform_tag") else None,
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
                artifact_bytes=int(model_data["artifact_bytes"])
                if model_data.get("artifact_bytes") is not None
                else None,
                file_count=int(model_data["file_count"]) if model_data.get("file_count") is not None else None,
                shard_count=int(model_data["shard_count"]) if model_data.get("shard_count") is not None else None,
                required_disk_bytes=int(model_data["required_disk_bytes"])
                if model_data.get("required_disk_bytes") is not None
                else None,
            ),
            package_indexes=tuple(
                PackageIndexFacts(
                    package=str(item["package"]),
                    index_url=str(item["index_url"]),
                    available_versions=tuple(str(version) for version in item.get("available_versions", ())),
                    error=str(item["error"]) if item.get("error") else None,
                    selected_version=str(item["selected_version"])
                    if item.get("selected_version")
                    else None,
                    artifacts=tuple(
                        PackageArtifactFacts(
                            filename=str(artifact["filename"]),
                            version=str(artifact["version"]),
                            kind=str(artifact["kind"]),
                            sha256=str(artifact["sha256"]) if artifact.get("sha256") else None,
                            python_tags=tuple(str(value) for value in artifact.get("python_tags", ())),
                            abi_tags=tuple(str(value) for value in artifact.get("abi_tags", ())),
                            platform_tags=tuple(str(value) for value in artifact.get("platform_tags", ())),
                            requires_python=str(artifact["requires_python"])
                            if artifact.get("requires_python")
                            else None,
                        )
                        for artifact in item.get("artifacts", ())
                    ),
                    compatibility_error=str(item["compatibility_error"])
                    if item.get("compatibility_error")
                    else None,
                )
                for item in facts_data.get("package_indexes", ())
            ),
            probe_errors=tuple(str(item) for item in facts_data.get("probe_errors", ())),
            host=HostExecutionFacts(
                hostname=str(host_data.get("hostname", "unknown")),
                cpu_architecture=str(host_data.get("cpu_architecture", "unknown")),
                logical_cpu_count=int(host_data.get("logical_cpu_count", 0)),
                physical_memory_bytes=int(host_data["physical_memory_bytes"])
                if host_data.get("physical_memory_bytes") is not None
                else None,
                available_memory_bytes=int(host_data["available_memory_bytes"])
                if host_data.get("available_memory_bytes") is not None
                else None,
                libc=str(host_data["libc"]) if host_data.get("libc") else None,
                libc_version=str(host_data["libc_version"]) if host_data.get("libc_version") else None,
                cgroup_memory_limit_bytes=int(host_data["cgroup_memory_limit_bytes"])
                if host_data.get("cgroup_memory_limit_bytes") is not None
                else None,
                cgroup_memory_current_bytes=int(host_data["cgroup_memory_current_bytes"])
                if host_data.get("cgroup_memory_current_bytes") is not None
                else None,
                nofile_soft=int(host_data["nofile_soft"]) if host_data.get("nofile_soft") is not None else None,
                nofile_hard=int(host_data["nofile_hard"]) if host_data.get("nofile_hard") is not None else None,
                pids_limit=int(host_data["pids_limit"]) if host_data.get("pids_limit") is not None else None,
                container_runtime=str(host_data["container_runtime"])
                if host_data.get("container_runtime")
                else None,
                errors=tuple(str(item) for item in host_data.get("errors", ())),
            ),
            fabric=GpuFabricFacts(
                topology=tuple(str(item) for item in fabric_data.get("topology", ())),
                nccl_version=str(fabric_data["nccl_version"])
                if fabric_data.get("nccl_version")
                else None,
                nccl_library=str(fabric_data["nccl_library"])
                if fabric_data.get("nccl_library")
                else None,
                errors=tuple(str(item) for item in fabric_data.get("errors", ())),
            ),
            storage=StorageCapabilityFacts(
                path=str(storage_data.get("path", "unknown")),
                total_bytes=int(storage_data["total_bytes"])
                if storage_data.get("total_bytes") is not None
                else None,
                free_bytes=int(storage_data["free_bytes"]) if storage_data.get("free_bytes") is not None else None,
                free_inodes=int(storage_data["free_inodes"])
                if storage_data.get("free_inodes") is not None
                else None,
                filesystem=str(storage_data["filesystem"]) if storage_data.get("filesystem") else None,
                device_identity=str(storage_data["device_identity"])
                if storage_data.get("device_identity")
                else None,
                readable=bool(storage_data.get("readable", False)),
                writable=bool(storage_data.get("writable", False)),
                errors=tuple(str(item) for item in storage_data.get("errors", ())),
            ),
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
