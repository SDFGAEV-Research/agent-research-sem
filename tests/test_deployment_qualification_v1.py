from pathlib import Path
import json

from research_platform.model.qualification.api import (
    CudaFacts,
    DeploymentCapabilityFacts,
    DeploymentQualificationRequest,
    GpuCapabilityFacts,
    GpuFabricFacts,
    HostExecutionFacts,
    ModelArtifactFacts,
    OperatingSystemFacts,
    PackageIndexFacts,
    PythonRuntimeFacts,
    StorageCapabilityFacts,
    CandidateDecision,
)
from research_platform.model.qualification.runtime.qualification import DeploymentQualificationResolver
from research_platform.operator.maintenance.runtime.management.deployments import _qualification_python_path
from research_platform.model.qualification.providers.qualification_probe import LocalDeploymentCapabilityProbe
from research_platform.platform.kernel.process import LocalCommandResult


def _facts(*, kernel_architectures: tuple[str, ...] = ("sm100",)) -> DeploymentCapabilityFacts:
    return DeploymentCapabilityFacts(
        captured_at_unix=1.0,
        operating_system=OperatingSystemFacts("Linux", "Ubuntu", "22.04", "6.8", "x86_64"),
        cuda=CudaFacts("580.173.02", "13.0", "12.4", ("12",)),
        gpus=(GpuCapabilityFacts("0", "GPU-0", "RTX 3090", 24576, 24000, "8.6"),),
        python=PythonRuntimeFacts(
            "/opt/python/bin/python",
            "3.11.0",
            "pip 26.0",
            True,
            True,
            "/opt/python/lib/python3.11/site-packages",
            "2.11.0",
            "13.0",
            kernel_architectures,
        ),
        model=ModelArtifactFacts(
            "qwen36-35b-a3b",
            "/models/qwen",
            "qwen3_5_moe",
            ("Qwen3_5MoeForConditionalGeneration",),
            "bfloat16",
            262144,
            True,
        ),
        package_indexes=(
            PackageIndexFacts("sglang", "https://pypi.org/simple", ("0.5.17",), selected_version="0.5.17"),
            PackageIndexFacts("vllm", "https://pypi.org/simple", ("0.27.1",), selected_version="0.27.1"),
            PackageIndexFacts(
                "sglang-kernel",
                "https://docs.sglang.io/whl/cu130/",
                ("0.4.6.post1+cu130",),
                selected_version="0.4.6.post1+cu130",
            ),
        ),
        host=HostExecutionFacts("test-host", "x86_64", 16, 128 << 30, 96 << 30),
        fabric=GpuFabricFacts(("GPU0 GPU1 NV1",), "2.18", "/usr/lib/libnccl.so.2"),
        storage=StorageCapabilityFacts("/models/qwen", 1 << 40, 512 << 30, 1_000_000, "xfs", "dev0", True, True),
    )


def test_resolver_rejects_observed_sglang_architecture_mismatch_and_selects_vllm() -> None:
    request = DeploymentQualificationRequest(
        "qwen36-35b-a3b",
        Path("/models/qwen"),
        Path("/opt/python/bin/python"),
        tensor_parallel=1,
    )

    plan = DeploymentQualificationResolver().resolve(request, _facts())

    sglang, vllm = plan.candidates
    assert sglang.decision is CandidateDecision.REJECTED
    assert "sm86" in " ".join(sglang.reasons)
    assert sglang.packages[0].version == "0.5.17"
    assert vllm.decision is CandidateDecision.ACCEPTED
    assert vllm.packages[0].name == "vllm"
    assert vllm.packages[0].version == "0.27.1"
    assert plan.selected_backend == "vllm"
    assert len(plan.plan_digest) == 64


def test_resolver_does_not_call_unobserved_kernel_support_qualified() -> None:
    request = DeploymentQualificationRequest(
        "qwen36-35b-a3b",
        Path("/models/qwen"),
        Path("/opt/python/bin/python"),
    )

    plan = DeploymentQualificationResolver().resolve(request, _facts(kernel_architectures=()))

    sglang = plan.candidates[0]
    assert sglang.decision is CandidateDecision.REJECTED
    assert "not observable yet" in " ".join(sglang.reasons)


def test_qualification_request_keeps_venv_interpreter_path_unresolved() -> None:
    # Resolving this path would erase the environment prefix when bin/python
    # is a symlink to the system interpreter.
    selected = _qualification_python_path(Path("/opt/envs/serving/bin/python"))
    assert str(selected).endswith("/opt/envs/serving/bin/python")


def test_package_index_qualification_consumes_artifact_metadata_without_install() -> None:
    class Runner:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        def run(self, argv, *, cwd=None, environment=None, timeout_seconds=None):
            self.calls.append(tuple(argv))
            if len(argv) >= 4 and argv[1:4] == ("-m", "pip", "index"):
                return LocalCommandResult(tuple(argv), 0, "Available versions: 1.2.3", "")
            return LocalCommandResult(
                tuple(argv),
                0,
                json.dumps(
                    {
                        "selected_version": "1.2.3",
                        "artifacts": [
                            {
                                "filename": "vllm-1.2.3-cp311-cp311-manylinux_2_28_x86_64.whl",
                                "version": "1.2.3",
                                "kind": "wheel",
                                "sha256": "a" * 64,
                                "python_tags": ["cp311"],
                                "abi_tags": ["cp311"],
                                "platform_tags": ["manylinux_2_28_x86_64"],
                                "requires_python": ">=3.11",
                            }
                        ],
                        "error": None,
                    }
                ),
                "",
            )

    runner = Runner()
    item = LocalDeploymentCapabilityProbe(runner)._index(
        Path("/opt/env/bin/python"), "vllm", "https://pypi.org/simple", 3.0
    )

    assert item.selected_version == "1.2.3"
    assert item.artifacts[0].sha256 == "a" * 64
    assert not any("install" in call for call in runner.calls)
