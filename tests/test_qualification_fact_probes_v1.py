from pathlib import Path

import research_platform.model.qualification.providers.qualification_host_probe as host_module
from research_platform.model.qualification.providers.qualification_accelerator_probe import AcceleratorFactsProbe
from research_platform.model.qualification.providers.qualification_host_probe import HostFactsProbe


def test_host_probe_captures_resource_values_without_controller(monkeypatch) -> None:
    monkeypatch.setattr(host_module.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(host_module.platform, "node", lambda: "qual-host")
    monkeypatch.setattr(host_module.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(host_module.platform, "libc_ver", lambda: ("glibc", "2.39"))
    monkeypatch.setattr(
        HostFactsProbe,
        "_meminfo_bytes",
        staticmethod(lambda key: {"MemTotal": 128 << 30, "MemAvailable": 96 << 30}[key]),
    )
    monkeypatch.setattr(
        HostFactsProbe,
        "_integer_file",
        staticmethod(lambda path: {"memory.max": 64 << 30, "memory.current": 8 << 30, "pids.max": 4096}.get(path.name)),
    )

    facts, errors = HostFactsProbe().host(2.0)

    assert facts.hostname == "qual-host"
    assert facts.logical_cpu_count == 12
    assert facts.physical_memory_bytes == 128 << 30
    assert facts.available_memory_bytes == 96 << 30
    assert facts.cgroup_memory_limit_bytes == 64 << 30
    assert facts.cgroup_memory_current_bytes == 8 << 30
    assert facts.pids_limit == 4096
    assert facts.libc == "glibc"
    assert tuple(errors) == facts.errors


def test_accelerator_probe_captures_cuda_and_gpu_facts() -> None:
    def run(argv, timeout):
        del timeout
        if argv[:2] == ("nvidia-smi", "--query-gpu=driver_version"):
            return 0, "580.173.02\n", ""
        if argv == ("nvidia-smi",):
            return 0, "CUDA Version: 13.0 NVIDIA Management Library Version: 580.173.02", ""
        if argv[:2] == ("nvcc", "--version"):
            return 0, "Cuda compilation tools, release 12.4, V12.4.131", ""
        if argv[:2] == ("ldconfig", "-p"):
            return 0, "libcudart.so.13.0 => /usr/lib/libcudart.so.13.0\nlibcuda.so.1 => /usr/lib/libcuda.so.1", ""
        if argv[0] == "nvidia-smi" and any("pci.bus_id" in item for item in argv):
            return 0, "0, GPU-0, RTX 3090, 24576, 24000, 00000000:01:00.0, 8.6, 350.0", ""
        if argv[0] == str(Path("/opt/python/bin/python")):
            return 0, "8.6\n", ""
        raise AssertionError(argv)

    probe = AcceleratorFactsProbe(run)
    cuda, cuda_errors = probe.cuda(2.0)

    assert cuda.driver_version == "580.173.02"
    assert cuda.driver_cuda_version == "13.0"
    assert cuda.toolkit_version == "12.4"
    assert cuda.runtime_library_versions == ("1", "13.0")
    assert cuda_errors == []


def test_accelerator_probe_parses_extended_gpu_row() -> None:
    from research_platform.model.qualification.api import DeploymentQualificationRequest, PythonRuntimeFacts

    def run(argv, timeout):
        del timeout
        if argv[0] == "nvidia-smi" and any("pci.bus_id" in item for item in argv):
            return 0, "0, GPU-0, RTX 3090, 24576, 24000, 00000000:01:00.0, 8.6, 350.0", ""
        if argv[0] == str(Path("/opt/python/bin/python")):
            return 0, "8.6\n", ""
        raise AssertionError(argv)

    request = DeploymentQualificationRequest(
        "model", Path("/models/model"), Path("/opt/python/bin/python")
    )
    python = PythonRuntimeFacts("/opt/python/bin/python", "3.11.0", None, False, False, None, None, None)
    gpus, errors = AcceleratorFactsProbe(run).gpus(request, python, 2.0)

    assert errors == []
    assert len(gpus) == 1
    assert gpus[0].uuid == "GPU-0"
    assert gpus[0].compute_capability == "8.6"
    assert gpus[0].pci_bus_id == "00000000:01:00.0"
    assert gpus[0].power_limit_watts == 350.0



def test_local_capability_probe_composes_split_fact_probes(tmp_path) -> None:
    import json
    from research_platform.model.qualification.api import DeploymentQualificationRequest
    from research_platform.model.qualification.providers.qualification_probe import LocalDeploymentCapabilityProbe
    from research_platform.platform.kernel.process import LocalCommandResult

    model_path = tmp_path / "model"
    model_path.mkdir()
    (model_path / "config.json").write_text(json.dumps({"model_type": "test", "architectures": ["TestModel"]}), encoding="utf-8")
    python_executable = Path("/opt/python/bin/python")

    class Runner:
        def run(self, argv, *, cwd=None, environment=None, timeout_seconds=None):
            del cwd, environment, timeout_seconds
            argv = tuple(argv)
            if len(argv) >= 3 and argv[1] == "-c" and "sysconfig.get_paths" in argv[2]:
                payload = {"version": "3.11.0", "site_packages": None, "torch_version": None, "kernel_architectures": [], "native_library_names": [], "python_abi": "cpython-311", "platform_tag": "test"}
                return LocalCommandResult(argv, 0, json.dumps(payload), "")
            if argv[1:4] == ("-m", "pip", "--version"):
                return LocalCommandResult(argv, 0, "pip 26.0", "")
            if argv[1:4] == ("-m", "ensurepip", "--version"):
                return LocalCommandResult(argv, 0, "pip 26.0", "")
            if len(argv) >= 3 and argv[1] == "-c" and "import venv" in argv[2]:
                return LocalCommandResult(argv, 0, "ok", "")
            return LocalCommandResult(argv, 1, "", "unavailable")

    facts = LocalDeploymentCapabilityProbe(Runner()).capture(
        DeploymentQualificationRequest("model", model_path, python_executable, backends=("dummy",), package_index_urls=("https://example.invalid/simple",), probe_timeout_seconds=1.0)
    )

    assert facts.model.config_present is True
    assert facts.python.version == "3.11.0"
    assert facts.host.logical_cpu_count >= 1
    assert facts.package_indexes[0].package == "dummy"
