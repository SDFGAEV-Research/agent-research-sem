from pathlib import Path

from research_platform.model.qualification.api import (
    CudaFacts,
    DeploymentCapabilityFacts,
    DeploymentQualificationRequest,
    GpuCapabilityFacts,
    ModelArtifactFacts,
    OperatingSystemFacts,
    PackageIndexFacts,
    PythonRuntimeFacts,
    CandidateDecision,
)
from research_platform.model.qualification.runtime.qualification import DeploymentQualificationResolver
from research_platform.operator.maintenance.runtime.management.deployments import _qualification_python_path


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
            PackageIndexFacts("sglang", "https://pypi.org/simple", ("0.5.17",)),
            PackageIndexFacts("vllm", "https://pypi.org/simple", ("0.27.1",)),
            PackageIndexFacts("sglang-kernel", "https://docs.sglang.io/whl/cu130/", ("0.4.6.post1+cu130",)),
        ),
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
