"""Local read-only capability probe adapter for model deployment qualification."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import sysconfig
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
    GpuFabricFacts,
    HostExecutionFacts,
    ModelArtifactFacts,
    OperatingSystemFacts,
    PackageArtifactFacts,
    PackageDependencyNodeFacts,
    PackageIndexFacts,
    PythonRuntimeFacts,
    StorageCapabilityFacts,
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
        host, host_errors = self._host(request.probe_timeout_seconds)
        errors.extend(host_errors)
        python, python_errors = self._python(request.python_executable, request.probe_timeout_seconds)
        errors.extend(python_errors)
        gpus, gpu_errors = self._gpus(request, python, request.probe_timeout_seconds)
        errors.extend(gpu_errors)
        fabric, fabric_errors = self._fabric(request.python_executable, request.probe_timeout_seconds)
        errors.extend(fabric_errors)
        model, model_error = self._model(request)
        if model_error:
            errors.append(model_error)
        storage, storage_errors = self._storage(request.model_path, request.probe_timeout_seconds)
        errors.extend(storage_errors)
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
            host=host,
            fabric=fabric,
            storage=storage,
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
        nvml = None
        code, out, _ = self._run(
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
            nvml_match = re.search(r"NVIDIA Management Library Version:\s*([^\s]+)", out)
            nvml = nvml_match.group(1) if nvml_match else None
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
        runtime_libraries = self._cuda_runtime_libraries(timeout)
        return CudaFacts(driver, driver_cuda, toolkit, nvrtc, (), nvml, runtime_libraries), errors

    def _cuda_runtime_libraries(self, timeout: float) -> tuple[str, ...]:
        code, out, _ = self._run(("ldconfig", "-p"), timeout)
        if code != 0:
            return ()
        values = {
            match.group(1)
            for line in out.splitlines()
            if (match := re.search(r"lib(?:cudart|cuda)\.so\.([0-9.]+)", line))
        }
        return tuple(sorted(values))

    @staticmethod
    def _integer_file(path: Path) -> int | None:
        try:
            value = path.read_text("utf-8", errors="replace").strip()
        except OSError:
            return None
        if value in {"", "max"}:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _meminfo_bytes(key: str) -> int | None:
        path = Path("/proc/meminfo")
        if not path.is_file():
            return None
        try:
            lines = path.read_text("utf-8", errors="replace").splitlines()
        except OSError:
            return None
        for line in lines:
            name, separator, raw = line.partition(":")
            if name != key or not separator:
                continue
            match = re.search(r"(\d+)", raw)
            if not match:
                return None
            return int(match.group(1)) * 1024
        return None

    def _host(self, timeout: float) -> tuple[HostExecutionFacts, list[str]]:
        errors: list[str] = []
        logical = os.cpu_count() or 0
        if logical == 0:
            errors.append("logical CPU count unavailable")
        physical = self._meminfo_bytes("MemTotal")
        available = self._meminfo_bytes("MemAvailable")
        if physical is None:
            errors.append("physical memory total unavailable")
        if available is None:
            errors.append("available memory unavailable")

        libc, libc_version = platform.libc_ver()
        libc = libc or None
        libc_version = libc_version or None
        if libc is None:
            errors.append("libc identity unavailable")

        memory_limit = self._integer_file(Path("/sys/fs/cgroup/memory.max"))
        memory_current = self._integer_file(Path("/sys/fs/cgroup/memory.current"))
        if not Path("/sys/fs/cgroup/memory.max").is_file():
            errors.append("cgroup memory limit unavailable")
        pids_limit = self._integer_file(Path("/sys/fs/cgroup/pids.max"))
        if not Path("/sys/fs/cgroup/pids.max").is_file():
            errors.append("cgroup pids limit unavailable")

        nofile_soft: int | None = None
        nofile_hard: int | None = None
        try:
            import resource

            nofile_soft, nofile_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        except (ImportError, AttributeError, OSError):
            errors.append("nofile limits unavailable")

        container = os.environ.get("container")
        if not container:
            if Path("/.dockerenv").exists():
                container = "docker"
            elif Path("/run/.containerenv").exists():
                container = "podman"

        # ``timeout`` is retained in the signature so every host probe shares
        # one bounded operation budget; local facts themselves are read-only.
        _ = timeout
        return HostExecutionFacts(
            hostname=platform.node() or "unknown",
            cpu_architecture=platform.machine() or "unknown",
            logical_cpu_count=logical,
            physical_memory_bytes=physical,
            available_memory_bytes=available,
            libc=libc,
            libc_version=libc_version,
            cgroup_memory_limit_bytes=memory_limit,
            cgroup_memory_current_bytes=memory_current,
            nofile_soft=nofile_soft,
            nofile_hard=nofile_hard,
            pids_limit=pids_limit,
            container_runtime=container,
            errors=tuple(errors),
        ), errors

    def _python(self, executable: Path, timeout: float) -> tuple[PythonRuntimeFacts, list[str]]:
        errors: list[str] = []
        info_code = (
            "import glob, importlib.metadata, json, pathlib, sys, sysconfig\n"
            "p = sysconfig.get_paths().get('purelib')\n"
            "a = sorted({pathlib.Path(x).parent.name for x in glob.glob((p or '') + '/sgl_kernel/sm*/common_ops.*')})\n"
            "t = next((d.version for d in importlib.metadata.distributions() if (d.metadata.get('Name') or '').lower() == 'torch'), None)\n"
            "print(json.dumps({'version': '.'.join(map(str, sys.version_info[:3])), 'site_packages': p, 'torch_version': t, 'kernel_architectures': a, 'python_abi': getattr(sys.implementation, 'cache_tag', None), 'platform_tag': sysconfig.get_platform()}))\n"
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
            python_abi=str(info["python_abi"]) if info.get("python_abi") else None,
            platform_tag=str(info["platform_tag"]) if info.get("platform_tag") else None,
        ), errors

    def _gpus(
        self,
        request: DeploymentQualificationRequest,
        python: PythonRuntimeFacts,
        timeout: float,
    ) -> tuple[tuple[GpuCapabilityFacts, ...], list[str]]:
        errors: list[str] = []
        query = (
            "nvidia-smi",
            "--query-gpu=index,uuid,name,memory.total,memory.free,pci.bus_id,compute_cap,power.limit",
            "--format=csv,noheader,nounits",
        )
        code, out, err = self._run(query, timeout)
        query_mode = "extended" if code == 0 else "compute"
        if code != 0:
            errors.append("nvidia-smi GPU capability query failed")
            code, out, err = self._run(
                (
                    "nvidia-smi",
                    "--query-gpu=index,uuid,name,memory.total,memory.free,compute_cap",
                    "--format=csv,noheader,nounits",
                ),
                timeout,
            )
            query_mode = "compute" if code == 0 else "basic"
        if code != 0:
            code, out, err = self._run(
                (
                    "nvidia-smi",
                    "--query-gpu=index,uuid,name,memory.total,memory.free",
                    "--format=csv,noheader,nounits",
                ),
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
            pci_bus_id = None
            power_limit = None
            cap_index = 5
            if query_mode == "extended":
                pci_bus_id = row[5] if len(row) > 5 and row[5] not in {"N/A", "[Not Supported]"} else None
                cap_index = 6
                if len(row) > 7 and row[7] not in {"N/A", "[Not Supported]"}:
                    try:
                        power_limit = float(row[7])
                    except ValueError:
                        errors.append(f"invalid GPU power limit row {row_index}")
            cap = row[cap_index] if len(row) > cap_index and row[cap_index] not in {"N/A", "[Not Supported]"} else None
            if cap is None and row_index < len(torch_caps):
                cap = torch_caps[row_index]
            try:
                values.append(
                    GpuCapabilityFacts(
                        row[0],
                        row[1],
                        row[2],
                        int(row[3]),
                        int(row[4]),
                        cap,
                        pci_bus_id,
                        self._pci_numa_node(pci_bus_id),
                        power_limit,
                    )
                )
            except ValueError:
                errors.append(f"invalid nvidia-smi GPU row {row_index}")
        return tuple(values), errors

    @staticmethod
    def _pci_numa_node(pci_bus_id: str | None) -> int | None:
        if not pci_bus_id:
            return None
        normalized = pci_bus_id
        if re.fullmatch(r"[0-9a-fA-F]{8}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]", normalized):
            normalized = normalized[4:]
        path = Path("/sys/bus/pci/devices") / normalized / "numa_node"
        try:
            value = path.read_text("utf-8", errors="replace").strip()
            return int(value) if value else None
        except (OSError, ValueError):
            return None

    def _torch_capabilities(self, executable: Path, timeout: float) -> tuple[str, ...]:
        code, out, err = self._run(
            (str(executable), "-c", "import torch; print('\\n'.join('%d.%d'%torch.cuda.get_device_capability(i) for i in range(torch.cuda.device_count())))"),
            timeout,
        )
        return tuple(line.strip() for line in out.splitlines() if re.fullmatch(r"\d+\.\d+", line.strip())) if code == 0 else ()

    def _fabric(self, executable: Path, timeout: float) -> tuple[GpuFabricFacts, list[str]]:
        errors: list[str] = []
        code, out, _ = self._run(("nvidia-smi", "topo", "-m"), timeout)
        topology = (
            tuple(
                re.sub(r"\x1b\[[0-9;]*m", "", line).rstrip()
                for line in out.splitlines()
                if line.strip()
            )
            if code == 0
            else ()
        )
        if not topology:
            errors.append("NVIDIA GPU topology query unavailable")

        nccl_version = None
        code, out, _ = self._run(
            (
                str(executable),
                "-c",
                "import torch; value = getattr(torch.cuda.nccl, 'version', lambda: None)(); print(value or '')",
            ),
            timeout,
        )
        if code == 0:
            nccl_version = next((line.strip() for line in out.splitlines() if line.strip()), None)
        if not nccl_version:
            errors.append("target Python NCCL version unavailable")

        nccl_library = None
        code, out, _ = self._run(("ldconfig", "-p"), timeout)
        if code == 0:
            nccl_library = next(
                (
                    line.strip()
                    for line in out.splitlines()
                    if "libnccl.so" in line and "=>" in line
                ),
                None,
            )
        if not nccl_library:
            errors.append("system NCCL library identity unavailable")
        return GpuFabricFacts(topology, nccl_version, nccl_library, tuple(errors)), errors

    def _storage(self, path: Path, timeout: float) -> tuple[StorageCapabilityFacts, list[str]]:
        errors: list[str] = []
        target = path if path.exists() else path.parent
        total = free = free_inodes = None
        try:
            usage = shutil.disk_usage(target)
            total, free = usage.total, usage.free
        except OSError:
            errors.append("model-path filesystem capacity unavailable")
        try:
            stat = os.statvfs(target)
            free_inodes = int(stat.f_favail)
        except (AttributeError, OSError):
            errors.append("model-path free inode count unavailable")

        filesystem = None
        device_identity = None
        code, out, _ = self._run(
            ("findmnt", "-T", str(target), "-n", "-o", "SOURCE,FSTYPE"),
            timeout,
        )
        if code == 0:
            line = next((item.strip() for item in out.splitlines() if item.strip()), "")
            fields = line.split(None, 1)
            if fields:
                device_identity = fields[0]
            if len(fields) > 1:
                filesystem = fields[1]
        else:
            errors.append("model-path filesystem identity unavailable")

        if not path.exists():
            errors.append("model path does not exist")
        readable = path.exists() and os.access(path, os.R_OK)
        writable = path.exists() and os.access(path, os.W_OK)
        if not readable:
            errors.append("model path is not readable")
        return StorageCapabilityFacts(
            path=str(path),
            total_bytes=total,
            free_bytes=free,
            free_inodes=free_inodes,
            filesystem=filesystem,
            device_identity=device_identity,
            readable=readable,
            writable=writable,
            errors=tuple(errors),
        ), errors

    @staticmethod
    def _artifact_stats(path: Path) -> tuple[int | None, int | None, int | None]:
        if not path.is_dir():
            return None, None, None
        total = 0
        files = 0
        shards = 0
        try:
            for item in path.rglob("*"):
                if not item.is_file():
                    continue
                files += 1
                total += item.stat().st_size
                if item.suffix.lower() in {".safetensors", ".bin", ".pt", ".pth"}:
                    shards += 1
        except OSError:
            return None, None, None
        return total, files, shards

    @classmethod
    def _model(cls, request: DeploymentQualificationRequest) -> tuple[ModelArtifactFacts, str | None]:
        path = request.model_path
        artifact_bytes, file_count, shard_count = cls._artifact_stats(path)
        config = path / "config.json"
        if not config.is_file():
            return ModelArtifactFacts(
                request.model_id,
                str(path),
                None,
                (),
                None,
                None,
                False,
                "model config.json is missing",
                artifact_bytes,
                file_count,
                shard_count,
                artifact_bytes,
            ), "model config.json is missing"
        try:
            data = json.loads(config.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ModelArtifactFacts(
                request.model_id,
                str(path),
                None,
                (),
                None,
                None,
                False,
                type(exc).__name__,
                artifact_bytes,
                file_count,
                shard_count,
                artifact_bytes,
            ), "model config.json could not be parsed"
        context = next((data.get(key) for key in ("max_position_embeddings", "max_sequence_length", "max_seq_len") if data.get(key) is not None), None)
        return ModelArtifactFacts(
            request.model_id,
            str(path),
            str(data["model_type"]) if data.get("model_type") else None,
            tuple(str(x) for x in data.get("architectures", ())),
            str(data["torch_dtype"]) if data.get("torch_dtype") else None,
            int(context) if context is not None else None,
            True,
            None,
            artifact_bytes,
            file_count,
            shard_count,
            artifact_bytes,
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
        available = tuple(dict.fromkeys(versions))
        snapshot = self._simple_index_snapshot(python, package, index_url, available, timeout)
        if snapshot is None:
            return PackageIndexFacts(
                package,
                index_url,
                available,
                selected_version=None,
                compatibility_error="simple package index artifact metadata was unavailable",
            )
        return PackageIndexFacts(
            package,
            index_url,
            available,
            selected_version=(
                str(snapshot["selected_version"])
                if snapshot.get("selected_version")
                else None
            ),
            artifacts=tuple(snapshot["artifacts"]),
            compatibility_error=(
                str(snapshot["error"]) if snapshot.get("error") else None
            ),
            dependency_nodes=tuple(snapshot["dependency_nodes"]),
            dependency_closure_complete=bool(snapshot.get("dependency_closure_complete", False)),
            dependency_closure_error=(
                str(snapshot["dependency_closure_error"])
                if snapshot.get("dependency_closure_error")
                else None
            ),
        )

    def _simple_index_snapshot(
        self,
        python: Path,
        package: str,
        index_url: str,
        available_versions: tuple[str, ...],
        timeout: float,
    ) -> dict[str, object] | None:
        """Read simple-index links and target-Python tags without downloading wheels."""

        script = r'''
import email.parser
import hashlib
import html.parser
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

try:
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.tags import sys_tags
    from packaging.utils import parse_wheel_filename
    from packaging.version import Version
except Exception as exc:
    print(json.dumps({"error": "target Python lacks packaging metadata parser: " + type(exc).__name__}))
    raise SystemExit(0)


MAX_NODES = 512
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_METADATA_WORKERS = 16
TARGET_ENVIRONMENT = default_environment()
TARGET_ENVIRONMENT["extra"] = ""


class _Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        values = dict(attrs)
        if values.get("href"):
            self.links.append(values)


def _fetch_url(url, accept, limit):
    """Fetch bounded index metadata without changing the target ABI probe."""
    errors = []
    curl = shutil.which("curl")
    if curl:
        try:
            result = subprocess.run(
                (
                    curl,
                    "--fail",
                    "--location",
                    "--silent",
                    "--show-error",
                    "--connect-timeout",
                    "5",
                    "--max-time",
                    "10",
                    "--max-filesize",
                    str(limit),
                    "--header",
                    "Accept: " + accept,
                    url,
                ),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=12,
            )
            if len(result.stdout) > limit:
                raise ValueError("metadata response exceeds observation limit")
            return result.stdout
        except Exception as exc:
            errors.append("curl:" + type(exc).__name__)
    try:
        request = Request(url, headers={"Accept": accept})
        with urlopen(request, timeout=10) as response:
            return response.read(limit)
    except Exception as exc:
        errors.append("urllib:" + type(exc).__name__)
        raise RuntimeError("bounded metadata fetch failed: " + ",".join(errors))


def _versions(raw):
    result = []
    for value in raw:
        try:
            version = str(Version(value))
        except Exception:
            continue
        if version not in result:
            result.append(version)
    return result


def _package_path(package):
    return package.replace("_", "-").replace(".", "-")


def _sha256_fragment(href):
    for value in urlsplit(href).fragment.split("&"):
        if value.startswith("sha256="):
            return value.split("=", 1)[1]
    return None


def _compatible_python(requires_python):
    if not requires_python:
        return True
    try:
        return SpecifierSet(requires_python).contains(
            Version("%d.%d.%d" % sys.version_info[:3]), prereleases=True
        )
    except Exception:
        return False


def _simple(index_url, package, page_cache):
    key = (index_url, package.lower().replace("_", "-"))
    if key in page_cache:
        return page_cache[key]
    url = urljoin(index_url.rstrip("/") + "/", _package_path(package) + "/")
    try:
        page = _fetch_url(url, "text/html", MAX_PAGE_BYTES + 1)
        if len(page) > MAX_PAGE_BYTES:
            raise ValueError("simple index page exceeds observation limit")
        parser = _Links()
        parser.feed(page.decode("utf-8", "replace"))
        page_cache[key] = (parser.links, None)
    except Exception as exc:
        page_cache[key] = ((), "simple index request failed: " + type(exc).__name__)
    return page_cache[key]


def _artifact(link, version_specifier, target_tags):
    href = link.get("href", "")
    raw_name = unquote(urlsplit(href).path.rsplit("/", 1)[-1])
    if not raw_name.endswith(".whl"):
        return None
    try:
        _name, version, _build, tags = parse_wheel_filename(raw_name)
    except Exception:
        return None
    normalized_version = str(version)
    if version_specifier and not version_specifier.contains(version, prereleases=True):
        return None
    requires_python = link.get("data-requires-python")
    wheel_tags = {str(tag) for tag in tags}
    if not (wheel_tags & target_tags) or not _compatible_python(requires_python):
        return None
    return {
        "filename": raw_name,
        "version": normalized_version,
        "kind": "wheel",
        "sha256": _sha256_fragment(href),
        "metadata_sha256": (
            str(link.get("data-dist-info-metadata") or link.get("data-core-metadata"))
            .removeprefix("sha256=")
            if link.get("data-dist-info-metadata") or link.get("data-core-metadata")
            else None
        ),
        "python_tags": sorted({str(tag).split("-")[0] for tag in wheel_tags}),
        "abi_tags": sorted({str(tag).split("-")[1] for tag in wheel_tags}),
        "platform_tags": sorted({str(tag).split("-")[2] for tag in wheel_tags}),
        "requires_python": requires_python,
        "dependency_requirements": [],
        "_href": href,
    }


def _select(index_url, package, specifier, version_hints, page_cache, target_tags):
    links, error = _simple(index_url, package, page_cache)
    if error:
        return None, (), error
    hints = set(_versions(version_hints))
    candidates = []
    for link in links:
        item = _artifact(link, specifier, target_tags)
        if item is not None and (not hints or item["version"] in hints):
            candidates.append(item)
    if not candidates and hints:
        # Index output can normalize local versions differently from the simple
        # filename. Re-run without the hint set but preserve the requirement.
        for link in links:
            item = _artifact(link, specifier, target_tags)
            if item is not None:
                candidates.append(item)
    if not candidates:
        return None, (), "no compatible binary wheel satisfies the requirement"
    selected = max((item["version"] for item in candidates), key=Version)
    selected_items = sorted(
        [item for item in candidates if item["version"] == selected],
        key=lambda item: item["filename"],
    )
    return selected, selected_items, None


def _read_metadata(artifact, metadata_cache):
    href = artifact["_href"].split("#", 1)[0] + ".metadata"
    if href in metadata_cache:
        deps, error = metadata_cache[href]
    else:
        try:
            body = _fetch_url(href, "application/octet-stream", MAX_METADATA_BYTES + 1)
            if len(body) > MAX_METADATA_BYTES:
                raise ValueError("package metadata exceeds observation limit")
            expected = artifact.get("metadata_sha256")
            if expected and hashlib.sha256(body).hexdigest() != expected:
                raise ValueError("package metadata SHA-256 mismatch")
            message = email.parser.BytesParser().parsebytes(body)
            deps = tuple(message.get_all("Requires-Dist", ()))
            error = None
        except Exception as exc:
            deps = ()
            error = "package metadata request failed: " + type(exc).__name__
        metadata_cache[href] = (deps, error)
    artifact["dependency_requirements"] = list(deps)
    return deps, error


def _public_artifact(item):
    return {key: value for key, value in item.items() if not key.startswith("_")}


index_url, package, raw_versions, fallback_index = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4]
page_cache = {}
metadata_cache = {}
target_tags = {str(tag) for tag in sys_tags()}
root_version, root_artifacts, root_error = _select(
    index_url, package, None, raw_versions, page_cache, target_tags
)
if root_error:
    print(json.dumps({
        "selected_version": None,
        "artifacts": [],
        "dependency_nodes": [],
        "dependency_closure_complete": False,
        "dependency_closure_error": root_error,
        "error": root_error,
    }, sort_keys=True))
    raise SystemExit(0)

root_artifact = root_artifacts[0]
root_deps, root_metadata_error = _read_metadata(root_artifact, metadata_cache)
root_name = package.lower().replace("_", "-")
selected = {
    root_name: {
        "package": root_name,
        "version": root_version,
        "index_url": index_url,
        "artifact": root_artifact,
        "dependencies": root_deps,
    }
}
order = [root_name]
index_hints = {root_name: index_url}
closure_error = root_metadata_error
iteration = 0


def _resolve_constrained_package(entry):
    normalized, specifier_text, index_hint = entry
    existing = selected.get(normalized)
    try:
        combined = SpecifierSet(specifier_text) if specifier_text else None
    except Exception:
        return normalized, None, True, "dependency closure requirement evaluation failed for " + normalized
    if existing is not None:
        if combined is None or combined.contains(Version(existing["version"]), prereleases=True):
            return normalized, existing, False, None
        if normalized == root_name:
            return normalized, None, True, "dependency closure constraints conflict with root package " + normalized
    candidate = None
    selected_index = index_hint
    indexes = [index_hint]
    if fallback_index not in indexes:
        indexes.append(fallback_index)
    for dependency_index in indexes:
        observed = _select(
            dependency_index,
            normalized,
            combined,
            (),
            page_cache,
            target_tags,
        )
        if observed[0] is not None and observed[1]:
            candidate = observed
            selected_index = dependency_index
            break
    if candidate is None:
        candidate = (None, (), None)
    if candidate[0] is None or not candidate[1]:
        return (
            normalized,
            None,
            True,
            "no compatible binary wheel satisfies all requirements for "
            + normalized
            + (": " + specifier_text if specifier_text else ""),
        )
    dependency_version, dependency_artifacts, dependency_error = candidate
    if dependency_error:
        return normalized, None, True, dependency_error + ": " + normalized
    dependency_artifact = dependency_artifacts[0]
    dependency_deps, dependency_metadata_error = _read_metadata(
        dependency_artifact, metadata_cache
    )
    if dependency_metadata_error:
        return normalized, None, True, dependency_metadata_error + ": " + normalized
    return (
        normalized,
        {
            "package": normalized,
            "version": dependency_version,
            "index_url": selected_index,
            "artifact": dependency_artifact,
            "dependencies": dependency_deps,
        },
        existing is None or existing["version"] != dependency_version,
        None,
    )


while closure_error is None:
    iteration += 1
    if iteration > MAX_NODES or len(selected) > MAX_NODES:
        closure_error = "dependency closure exceeds observation limit"
        break
    constraints = {}
    constraint_text = {}
    for current_name in tuple(order):
        current = selected[current_name]
        for raw_requirement in current["dependencies"]:
            try:
                requirement = Requirement(raw_requirement)
            except Exception:
                closure_error = "invalid dependency requirement: " + raw_requirement
                break
            if requirement.marker is not None and not requirement.marker.evaluate(TARGET_ENVIRONMENT):
                continue
            if requirement.url:
                closure_error = "direct URL dependency is not reproducibly indexed: " + requirement.name
                break
            normalized = requirement.name.lower().replace("_", "-")
            constraints.setdefault(normalized, []).append(str(requirement.specifier))
            constraint_text.setdefault(normalized, []).append(
                str(requirement.specifier) or "any"
            )
            index_hints.setdefault(normalized, current["index_url"])
        if closure_error is not None:
            break
    if closure_error is not None:
        break
    entries = tuple(
        (
            normalized,
            ",".join(value for value in values if value),
            index_hints[normalized],
        )
        for normalized, values in constraints.items()
    )
    with ThreadPoolExecutor(max_workers=MAX_METADATA_WORKERS) as executor:
        resolved = tuple(executor.map(_resolve_constrained_package, entries))
    changed = False
    for normalized, node, node_changed, node_error in resolved:
        if node_error:
            closure_error = node_error + (
                " [constraints=" + ",".join(constraint_text.get(normalized, ())) + "]"
                if constraint_text.get(normalized)
                else ""
            )
            break
        if node_changed:
            selected[normalized] = node
            if normalized not in order:
                order.append(normalized)
            changed = True
    if closure_error is not None or not changed:
        break

nodes = [
    {
        "package": normalized,
        "version": selected[normalized]["version"],
        "index_url": selected[normalized]["index_url"],
        "artifact": _public_artifact(selected[normalized]["artifact"]),
    }
    for normalized in order
]

print(json.dumps({
    "selected_version": root_version,
    "artifacts": [_public_artifact(item) for item in root_artifacts],
    "dependency_nodes": nodes,
    "dependency_closure_complete": closure_error is None,
    "dependency_closure_error": closure_error,
    "error": None,
}, sort_keys=True))
'''
        code, out, err = self._run(
            (
                str(python),
                "-c",
                script,
                index_url,
                package,
                json.dumps(available_versions),
                PYPI_SIMPLE,
            ),
            timeout,
        )
        if code != 0:
            raw_detail = str(err or out or "")
            detail = raw_detail.strip().splitlines()[-1] if raw_detail.strip() else f"exit={code}"
            return {
                "selected_version": None,
                "artifacts": (),
                "dependency_nodes": (),
                "dependency_closure_complete": False,
                "dependency_closure_error": f"target simple-index probe failed: {detail[:240]}",
                "error": f"target simple-index probe failed: {detail[:240]}",
            }
        try:
            raw_output = str(out or "")
            payload = json.loads(raw_output.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            detail = raw_output.strip().splitlines()[-1] if raw_output.strip() else "empty probe output"
            return {
                "selected_version": None,
                "artifacts": (),
                "dependency_nodes": (),
                "dependency_closure_complete": False,
                "dependency_closure_error": f"target simple-index probe returned invalid JSON: {detail[:240]}",
                "error": f"target simple-index probe returned invalid JSON: {detail[:240]}",
            }
        if payload.get("error") and not payload.get("artifacts"):
            return {
                "selected_version": None,
                "artifacts": (),
                "dependency_nodes": (),
                "dependency_closure_complete": False,
                "dependency_closure_error": str(payload["error"]),
                "error": str(payload["error"]),
            }
        artifacts = tuple(
            PackageArtifactFacts(
                filename=str(item["filename"]),
                version=str(item["version"]),
                kind=str(item["kind"]),
                sha256=str(item["sha256"]) if item.get("sha256") else None,
                python_tags=tuple(str(value) for value in item.get("python_tags", ())),
                abi_tags=tuple(str(value) for value in item.get("abi_tags", ())),
                platform_tags=tuple(str(value) for value in item.get("platform_tags", ())),
                requires_python=str(item["requires_python"])
                if item.get("requires_python")
                else None,
                metadata_sha256=str(item["metadata_sha256"])
                if item.get("metadata_sha256")
                else None,
                dependency_requirements=tuple(
                    str(value) for value in item.get("dependency_requirements", ())
                ),
            )
            for item in payload.get("artifacts", ())
        )
        dependency_nodes = tuple(
            PackageDependencyNodeFacts(
                package=str(node["package"]),
                version=str(node["version"]),
                index_url=str(node["index_url"]),
                artifact=PackageArtifactFacts(
                    filename=str(node["artifact"]["filename"]),
                    version=str(node["artifact"]["version"]),
                    kind=str(node["artifact"]["kind"]),
                    sha256=str(node["artifact"]["sha256"])
                    if node["artifact"].get("sha256")
                    else None,
                    python_tags=tuple(
                        str(value) for value in node["artifact"].get("python_tags", ())
                    ),
                    abi_tags=tuple(
                        str(value) for value in node["artifact"].get("abi_tags", ())
                    ),
                    platform_tags=tuple(
                        str(value) for value in node["artifact"].get("platform_tags", ())
                    ),
                    requires_python=str(node["artifact"]["requires_python"])
                    if node["artifact"].get("requires_python")
                    else None,
                    metadata_sha256=str(node["artifact"]["metadata_sha256"])
                    if node["artifact"].get("metadata_sha256")
                    else None,
                    dependency_requirements=tuple(
                        str(value)
                        for value in node["artifact"].get("dependency_requirements", ())
                    ),
                ),
            )
            for node in payload.get("dependency_nodes", ())
        )
        return {
            "selected_version": payload.get("selected_version"),
            "artifacts": artifacts,
            "dependency_nodes": dependency_nodes,
            "dependency_closure_complete": bool(payload.get("dependency_closure_complete", False)),
            "dependency_closure_error": payload.get("dependency_closure_error"),
            "error": payload.get("error"),
        }

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
