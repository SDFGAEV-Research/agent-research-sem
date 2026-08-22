from pathlib import Path

from research_platform.environment.python.api import EnvironmentCommandResult
from research_platform.model.qualification.api import (
    CudaFacts,
    DeploymentCapabilityFacts,
    DeploymentQualificationApplicationReceipt,
    DeploymentQualificationApplicationRequest,
    DeploymentQualificationEvidenceRecord,
    DeploymentQualificationRuntimeRequest,
    DeploymentRuntimeQualificationStatus,
    GpuCapabilityFacts,
    InstallPackage,
    ModelArtifactFacts,
    OperatingSystemFacts,
    PackageIndexFacts,
    PythonRuntimeFacts,
    QualificationCommandReceipt,
    QualificationMaterializationStatus,
    RuntimeCheckReceipt,
)
from research_platform.model.qualification.providers.qualification_application import (
    FileDeploymentQualificationApplicationStore,
)
from research_platform.model.qualification.providers.qualification_evidence import (
    FileDeploymentQualificationEvidenceStore,
)
from research_platform.model.qualification.providers.qualification_runtime import (
    FileDeploymentQualificationRuntimeStore,
)
from research_platform.model.qualification.providers.python_runtime_probe import (
    PythonEnvironmentRuntimeProbe,
)
from research_platform.model.qualification.runtime.qualification import DeploymentQualificationResolver
from research_platform.model.qualification.runtime.runtime_qualification import (
    DeploymentQualificationRuntimeVerifier,
)


class _Probe:
    def __init__(self, *, failed: bool = False) -> None:
        self.failed = failed
        self.calls: list[tuple[str, str, Path, int]] = []

    def probe(self, environment_id: str, backend: str, model_path: Path, tensor_parallel: int):
        self.calls.append((environment_id, backend, model_path, tensor_parallel))
        code = 1 if self.failed else 0
        return tuple(
            RuntimeCheckReceipt(name, "a" * 64, code, "b" * 64, "c" * 64)
            for name in ("backend-import", "cuda-runtime", "model-config")
        )


class _Execution:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, environment_id: str, *args: str, **kwargs):
        self.calls.append((environment_id, *args))
        return EnvironmentCommandResult(("/opt/env/bin/python", *args), 0, "{}", "")


def _request() -> object:
    from research_platform.model.qualification.api import DeploymentQualificationRequest

    return DeploymentQualificationRequest(
        "qwen36-35b-a3b",
        Path("/models/qwen"),
        Path("/opt/env/bin/python"),
        backends=("vllm",),
        tensor_parallel=2,
    )


def _facts() -> DeploymentCapabilityFacts:
    return DeploymentCapabilityFacts(
        captured_at_unix=1.0,
        operating_system=OperatingSystemFacts("Linux", "Ubuntu", "22.04", "6.8", "x86_64"),
        cuda=CudaFacts("580.173.02", "13.0", "12.4", ("12",)),
        gpus=(
            GpuCapabilityFacts("0", "GPU-0", "RTX 3090", 24576, 24000, "8.6"),
            GpuCapabilityFacts("1", "GPU-1", "RTX 3090", 24576, 24000, "8.6"),
        ),
        python=PythonRuntimeFacts(
            "/opt/env/bin/python", "3.11.0", "pip 26.0", True, True,
            "/opt/env/lib/python3.11/site-packages", "2.11.0", "13.0", ("sm86",),
        ),
        model=ModelArtifactFacts(
            "qwen36-35b-a3b", "/models/qwen", "qwen3_5_moe",
            ("Qwen3_5MoeForConditionalGeneration",), "bfloat16", 262144, True,
        ),
        package_indexes=(PackageIndexFacts("vllm", "https://pypi.org/simple", ("0.27.1",)),),
    )


def _seed(tmp_path: Path, status: QualificationMaterializationStatus):
    request = _request()
    facts = _facts()
    plan = DeploymentQualificationResolver().resolve(request, facts)
    evidence = FileDeploymentQualificationEvidenceStore(tmp_path / "evidence")
    evidence.publish(DeploymentQualificationEvidenceRecord(1.0, request, facts, plan))
    application_store = FileDeploymentQualificationApplicationStore(tmp_path / "applications")
    application = DeploymentQualificationApplicationReceipt(
        plan_digest=plan.plan_digest,
        environment_id="qwen-vllm",
        backend="vllm",
        packages=(InstallPackage("vllm", "0.27.1", "https://pypi.org/simple"),),
        install_commands=(QualificationCommandReceipt("pip-install", "d" * 64, 0, "e" * 64, "f" * 64),),
        check_command=QualificationCommandReceipt("pip-check", "g" * 64, 0, "h" * 64, "i" * 64),
        status=status,
    )
    application_store.publish(application)
    return plan, application, evidence, application_store


def test_runtime_verifier_runs_all_checks_and_persists_receipt(tmp_path: Path) -> None:
    _plan, application, evidence, applications = _seed(tmp_path, QualificationMaterializationStatus.SUCCEEDED)
    probe = _Probe()
    runtimes = FileDeploymentQualificationRuntimeStore(tmp_path / "runtime")
    receipt = DeploymentQualificationRuntimeVerifier(evidence, applications, probe, runtimes).qualify(
        DeploymentQualificationRuntimeRequest(application.application_digest)
    )

    assert receipt.status is DeploymentRuntimeQualificationStatus.PASSED
    assert len(receipt.checks) == 3
    assert probe.calls == [("qwen-vllm", "vllm", Path("/models/qwen"), 2)]
    assert runtimes.get(receipt.runtime_digest) == receipt


def test_runtime_verifier_blocks_unsuccessful_application_without_probe(tmp_path: Path) -> None:
    _plan, application, evidence, applications = _seed(tmp_path, QualificationMaterializationStatus.FAILED)
    probe = _Probe()
    runtimes = FileDeploymentQualificationRuntimeStore(tmp_path / "runtime")
    receipt = DeploymentQualificationRuntimeVerifier(evidence, applications, probe, runtimes).qualify(
        DeploymentQualificationRuntimeRequest(application.application_digest)
    )

    assert receipt.status is DeploymentRuntimeQualificationStatus.BLOCKED
    assert probe.calls == []


def test_python_runtime_probe_binds_tensor_parallel_and_model_path() -> None:
    execution = _Execution()
    checks = PythonEnvironmentRuntimeProbe(execution).probe(
        "qwen-vllm", "vllm", Path("/models/qwen"), 4
    )

    assert [item.check for item in checks] == ["backend-import", "cuda-runtime", "model-config"]
    assert execution.calls[1][-1] == "4"
    assert execution.calls[2][-1] == "/models/qwen"
