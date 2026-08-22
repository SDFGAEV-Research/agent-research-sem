"""Local read-only capability probe adapter for model deployment qualification."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import platform
import re
import sys
import time

from research_platform.platform.kernel.process import (
    LocalCommandRunnerPort,
    LocalCommandStartError,
    LocalCommandTimeoutError,
    SubprocessLocalCommandRunner,
)

from research_platform.model.qualification.api import (
    CudaFacts,
    DeploymentCapabilityFacts,
    DeploymentCapabilityProbePort,
    DeploymentQualificationRequest,
    GpuCapabilityFacts,
    ModelArtifactFacts,
    OperatingSystemFacts,
    PackageIndexFacts,
    PythonRuntimeFacts,
)

from ..runtime.qualification import PYPI_SIMPLE


_CUDA_CHANNELS = ("cu130", "cu129", "cu128", "cu124", "cu121", "cu118")
_SGLANG_KERNEL_INDEX = "https://docs.sglang.io/whl/{channel}/"


class LocalDeploymentCapabilityProbe(DeploymentCapabilityProbePort):
    """Capture host facts without installing, starting or mutating anything."""

    def __init__(self, runner: LocalCommandRunnerPort | None = None) -> None:
        self._runner = runner or SubprocessLocalCommandRunner()

    def capture(self, request: DeploymentQualificationRequest) -> DeploymentCapabilityFacts:
        errors: list[str] = []
        operating_system = self._operating_system()
        cuda, cuda_errors = self._cuda(request.probe_timeout_seconds)
        errors.extend(cuda_errors)
        python, python_errors = self._python(request.python_executable, request.probe_timeout_seconds)
        errors.extend(python_errors)
        gpus, gpu_errors = self._gpus(request, python, request.probe_timeout_seconds)
        errors.extend(gpu_errors)
        model, model_error = self._model(request)
        if model_error:
            errors.append(model_error)
        indexes = self._package_indexes(
            request,
            python,
            cuda,
            request.probe_timeout_seconds,
            errors,
        )
        return DeploymentCapabilityFacts(
            captured_at_unix=time.time(),
            operating_system=operating_system,
            cuda=cuda,
            gpus=gpus,
            python=python,
            model=model,
            package_indexes=indexes,
            probe_errors=tuple(errors),
        )

    def _run(self, argv: tuple[str, ...], timeout: float) -> tuple[int, str, str]:
        try:
            result = self._runner.run(
                argv,
                environment=os.environ.copy(),
                timeout_seconds=timeout,
            )
        except LocalCommandStartError:
            return 127, "", f"executable not found: {argv[0]}"
        except LocalCommandTimeoutError:
            return 124, "", f"command timed out: {argv[0]}"
        except OSError as exc:
            return 126, "", f"command failed: {argv[0]}: {type(exc).__name__}"
        return result.returncode, result.stdout, result.stderr

    @staticmethod
    def _operating_system() -> OperatingSystemFacts:
        values: dict[str, str] = {}
        path = Path("/etc/os-release")
        if path.is_file():
            for line in path.read_text("utf-8", errors="replace").splitlines():
                key, separator, value = line.partition("=")
                if separator:
                    values[key] = value.strip().strip('"')
        return OperatingSystemFacts(
            system=platform.system(),
            distribution=values.get("PRETTY_NAME", values.get("ID", "unknown")),
            distribution_version=values.get("VERSION_ID", "unknown"),
            kernel=platform.release(),
            machine=platform.machine(),
        )

    def _cuda(self, timeout: float) -> tuple[CudaFacts, list[str]]:
        errors: list[str] = []
        driver = None
        driver_cuda = None
        code, out, err = self._run(
            ("nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits"),
            timeout,
        )
        if code == 0:
            driver = next((line.strip() for line in out.splitlines() if line.strip()), None)
        else:
            errors.append("nvidia-smi driver query failed")
        code, out, err = self._run(("nvidia-smi",), timeout)
        if code == 0:
            match = re.search(r"CUDA Version:\s*([^\s]+)", out)
            driver_cuda = match.group(1) if match else None
        else:
            errors.append("nvidia-smi summary query failed")
        code, out, err = self._run(("nvcc", "--version"), timeout)
        toolkit = None
        if code == 0:
            match = re.search(r"release\s+([0-9.]+)", out)
            toolkit = match.group(1) if match else None
        else:
            errors.append("nvcc toolkit query unavailable")
        nvrtc_paths = []
        for root in (Path("/usr/local"), Path("/usr/lib")):
            if not root.exists():
                continue
            nvrtc_paths.extend(root.glob("cuda*/lib*/libnvrtc.so.*"))
            nvrtc_paths.extend(root.glob("lib*/libnvrtc.so.*"))
        nvrtc = tuple(
            sorted(
                {
                    match.group(1)
                    for path in nvrtc_paths
                    if (match := re.search(r"libnvrtc\.so\.([0-9.]+)$", path.name))
                }
            )
        )
        return CudaFacts(driver, driver_cuda, toolkit, nvrtc, ()), errors

    def _python(self, executable: Path, timeout: float) -> tuple[PythonRuntimeFacts, list[str]]:
        errors: list[str] = []
        info_code = (
            "import glob, importlib.metadata, json, pathlib, sys, sysconfig\n"
            "p = sysconfig.get_paths().get('purelib')\n"
            "a = sorted({pathlib.Path(x).parent.name for x in glob.glob((p or '') + '/sgl_kernel/sm*/common_ops.*')})\n"
            "t = next((d.version for d in importlib.metadata.distributions() if (d.metadata.get('Name') or '').lower() == 'torch'), None)\n"
            "print(json.dumps({'version': '.'.join(map(str, sys.version_info[:3])), 'site_packages': p, 'torch_version': t, 'kernel_architectures': a}))\n"
        )
        code, out, err = self._run((str(executable), "-c", info_code), timeout)
        info: dict[str, object] = {}
        if code == 0:
            try:
                info = json.loads(out.strip().splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                errors.append("Python capability probe returned invalid JSON")
        else:
            errors.append("Python capability probe failed")
        torch_cuda_version = None
        torch_code, torch_out, _ = self._run(
            (str(executable), "-c", "import torch; print(torch.version.cuda or '')"),
            timeout,
        )
        if torch_code == 0:
            torch_cuda_version = next((line.strip() for line in torch_out.splitlines() if line.strip()), None)
        code, out, err = self._run((str(executable), "-m", "pip", "--version"), timeout)
        pip_version = out.strip() if code == 0 else None
        if pip_version is None:
            errors.append("selected Python interpreter has no pip")
        code, out, err = self._run((str(executable), "-m", "ensurepip", "--version"), timeout)
        ensurepip = code == 0
        code, out, err = self._run((str(executable), "-c", "import venv; print('ok')"), timeout)
        venv = code == 0 and ensurepip
        if not venv:
            errors.append("selected Python interpreter has no usable venv bootstrap")
        return PythonRuntimeFacts(
            executable=str(executable),
            version=str(info.get("version", "unknown")),
            pip_version=pip_version,
            ensurepip_available=ensurepip,
            venv_available=venv,
            site_packages=str(info["site_packages"]) if info.get("site_packages") else None,
            torch_version=str(info["torch_version"]) if info.get("torch_version") else None,
            torch_cuda_version=torch_cuda_version,
            kernel_architectures=tuple(str(x) for x in info.get("kernel_architectures", ())),
            errors=tuple(errors),
        ), errors

    def _gpus(
        self,
        request: DeploymentQualificationRequest,
        python: PythonRuntimeFacts,
        timeout: float,
    ) -> tuple[tuple[GpuCapabilityFacts, ...], list[str]]:
        errors: list[str] = []
        query = (
            "nvidia-smi", "--query-gpu=index,uuid,name,memory.total,memory.free,compute_cap",
            "--format=csv,noheader,nounits",
        )
        code, out, err = self._run(query, timeout)
        include_compute = code == 0
        if not include_compute:
            errors.append("nvidia-smi GPU capability query failed")
            code, out, err = self._run(
                ("nvidia-smi", "--query-gpu=index,uuid,name,memory.total,memory.free", "--format=csv,noheader,nounits"),
                timeout,
            )
        if code != 0:
            return (), errors
        torch_caps = self._torch_capabilities(request.python_executable, timeout)
        values: list[GpuCapabilityFacts] = []
        for row_index, row in enumerate(csv.reader(out.splitlines())):
            row = [value.strip() for value in row]
            if len(row) < 5:
                continue
            cap = row[5] if include_compute and len(row) > 5 and row[5] not in {"N/A", "[Not Supported]"} else None
            if cap is None and row_index < len(torch_caps):
                cap = torch_caps[row_index]
            try:
                values.append(GpuCapabilityFacts(row[0], row[1], row[2], int(row[3]), int(row[4]), cap))
            except ValueError:
                errors.append(f"invalid nvidia-smi GPU row {row_index}")
        return tuple(values), errors

    def _torch_capabilities(self, executable: Path, timeout: float) -> tuple[str, ...]:
        code, out, err = self._run(
            (str(executable), "-c", "import torch; print('\\n'.join('%d.%d'%torch.cuda.get_device_capability(i) for i in range(torch.cuda.device_count())))"),
            timeout,
        )
        return tuple(line.strip() for line in out.splitlines() if re.fullmatch(r"\d+\.\d+", line.strip())) if code == 0 else ()

    @staticmethod
    def _model(request: DeploymentQualificationRequest) -> tuple[ModelArtifactFacts, str | None]:
        path = request.model_path
        config = path / "config.json"
        if not config.is_file():
            return ModelArtifactFacts(request.model_id, str(path), None, (), None, None, False, "model config.json is missing"), "model config.json is missing"
        try:
            data = json.loads(config.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ModelArtifactFacts(request.model_id, str(path), None, (), None, None, False, type(exc).__name__), "model config.json could not be parsed"
        context = next((data.get(key) for key in ("max_position_embeddings", "max_sequence_length", "max_seq_len") if data.get(key) is not None), None)
        return ModelArtifactFacts(
            request.model_id,
            str(path),
            str(data["model_type"]) if data.get("model_type") else None,
            tuple(str(x) for x in data.get("architectures", ())),
            str(data["torch_dtype"]) if data.get("torch_dtype") else None,
            int(context) if context is not None else None,
            True,
        ), None

    def _package_indexes(
        self,
        request: DeploymentQualificationRequest,
        python: PythonRuntimeFacts,
        cuda: CudaFacts,
        timeout: float,
        errors: list[str],
    ) -> tuple[PackageIndexFacts, ...]:
        packages = {backend.strip().lower() for backend in request.backends if backend.strip()}
        index_python = request.python_executable if python.pip_version else Path(sys.executable)
        if index_python != request.python_executable:
            errors.append("package indexes were queried with the controller Python because target Python has no pip")
        rows: list[PackageIndexFacts] = []
        for package in sorted(packages):
            for index_url in request.package_index_urls:
                rows.append(self._index(index_python, package, index_url, timeout))
        if "sglang" in packages:
            for channel in self._kernel_channels(cuda):
                rows.append(self._index(index_python, "sglang-kernel", _SGLANG_KERNEL_INDEX.format(channel=channel), timeout))
        return tuple(rows)

    def _index(self, python: Path, package: str, index_url: str, timeout: float) -> PackageIndexFacts:
        code, out, err = self._run((str(python), "-m", "pip", "index", "versions", package, "--index-url", index_url), timeout)
        if code != 0:
            detail = (err or out).strip().splitlines()[-1] if (err or out).strip() else f"exit={code}"
            return PackageIndexFacts(package, index_url, (), detail[:240])
        versions: list[str] = []
        match = re.search(r"Available versions:\s*(.+)", out)
        if match:
            versions.extend(value.strip() for value in match.group(1).split(",") if value.strip())
        if not versions:
            first = next((line.strip() for line in out.splitlines() if line.strip()), "")
            version = re.search(r"\(([^)]+)\)", first)
            if version:
                versions.append(version.group(1))
        return PackageIndexFacts(package, index_url, tuple(dict.fromkeys(versions)))

    @staticmethod
    def _kernel_channels(cuda: CudaFacts) -> tuple[str, ...]:
        preferred: list[str] = []
        for raw in (cuda.driver_cuda_version, cuda.toolkit_version):
            if raw:
                parts = raw.split(".")
                if len(parts) >= 2:
                    channel = f"cu{parts[0]}{parts[1]}"
                    if channel in _CUDA_CHANNELS and channel not in preferred:
                        preferred.append(channel)
        return tuple(preferred + [item for item in _CUDA_CHANNELS if item not in preferred])


__all__ = ["LocalDeploymentCapabilityProbe"]
