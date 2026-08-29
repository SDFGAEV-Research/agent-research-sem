"""Local read-only capability probe adapter for model deployment qualification."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time

from research_platform.platform.kernel.process import (
    LocalCommandRunnerPort,
    LocalCommandStartError,
    LocalCommandTimeoutError,
)

from research_platform.model.qualification.api import (
    CudaFacts,
    DeploymentCapabilityFacts,
    DeploymentCapabilityProbePort,
    DeploymentQualificationRequest,
    ModelArtifactFacts,
    PackageIndexFacts,
    PythonRuntimeFacts,
    StorageCapabilityFacts,
    DEFAULT_PACKAGE_INDEX_URL,
    native_cuda_runtime_package_names,
)

from .qualification_accelerator_probe import AcceleratorFactsProbe
from .qualification_host_probe import HostFactsProbe
from .qualification_index_snapshot import TargetPackageIndexSnapshotProbe

PYPI_SIMPLE = DEFAULT_PACKAGE_INDEX_URL


_CUDA_CHANNELS = ("cu130", "cu129", "cu128", "cu124", "cu121", "cu118")
_SGLANG_KERNEL_INDEX = "https://docs.sglang.io/whl/{channel}/"
_MAX_ROOT_CANDIDATE_ATTEMPTS = 24


class LocalDeploymentCapabilityProbe(DeploymentCapabilityProbePort):
    """Capture host facts without installing, starting or mutating anything."""

    def __init__(self, runner: LocalCommandRunnerPort) -> None:
        self._runner = runner
        self._index_snapshot = TargetPackageIndexSnapshotProbe(self._run)
        self._host_probe = HostFactsProbe()
        self._accelerator_probe = AcceleratorFactsProbe(self._run)

    def capture(self, request: DeploymentQualificationRequest) -> DeploymentCapabilityFacts:
        errors: list[str] = []
        operating_system = self._host_probe.operating_system()
        cuda, cuda_errors = self._accelerator_probe.cuda(request.probe_timeout_seconds)
        errors.extend(cuda_errors)
        host, host_errors = self._host_probe.host(request.probe_timeout_seconds)
        errors.extend(host_errors)
        python, python_errors = self._python(request.python_executable, request.probe_timeout_seconds)
        errors.extend(python_errors)
        gpus, gpu_errors = self._accelerator_probe.gpus(request, python, request.probe_timeout_seconds)
        errors.extend(gpu_errors)
        fabric, fabric_errors = self._accelerator_probe.fabric(request.python_executable, request.probe_timeout_seconds)
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







    def _python(self, executable: Path, timeout: float) -> tuple[PythonRuntimeFacts, list[str]]:
        errors: list[str] = []
        info_code = (
            "import glob, importlib.metadata, json, pathlib, sys, sysconfig\n"
            "p = sysconfig.get_paths().get('purelib')\n"
            "a = sorted({pathlib.Path(x).parent.name for x in glob.glob((p or '') + '/sgl_kernel/sm*/common_ops.*')})\n"
            "patterns = tuple((p or '') + '/**/' + name for name in ('libcudart.so*', 'libnvrtc.so*', 'libcublas.so*', 'libnccl.so*'))\n"
            "native = sorted({pathlib.Path(x).name for pattern in patterns for x in glob.glob(pattern, recursive=True)})\n"
            "t = next((d.version for d in importlib.metadata.distributions() if (d.metadata.get('Name') or '').lower() == 'torch'), None)\n"
            "print(json.dumps({'version': '.'.join(map(str, sys.version_info[:3])), 'site_packages': p, 'torch_version': t, 'kernel_architectures': a, 'native_library_names': native, 'python_abi': getattr(sys.implementation, 'cache_tag', None), 'platform_tag': sysconfig.get_platform()}))\n"
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
            native_library_names=tuple(
                str(x) for x in info.get("native_library_names", ())
            ),
        ), errors

    @staticmethod
    def _parse_package_index_urls(output: str) -> tuple[str, ...]:
        """Extract pip's configured primary and extra indexes deterministically."""

        values: list[str] = []
        for raw_line in output.splitlines():
            key, separator, raw_value = raw_line.partition("=")
            if not separator or not key.strip().lower().endswith(("index-url", "extra-index-url")):
                continue
            value = raw_value.strip().strip("'\"")
            if not value:
                continue
            for item in re.split(r"[\s,]+", value):
                normalized = item.strip().strip("'\"")
                if normalized and normalized not in values:
                    values.append(normalized)
        return tuple(values)





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
        raw_cuda_version = python.torch_cuda_version or cuda.driver_cuda_version or cuda.toolkit_version
        packages.update(native_cuda_runtime_package_names(raw_cuda_version))
        index_python = request.python_executable if python.pip_version else Path(sys.executable)
        if index_python != request.python_executable:
            errors.append("package indexes were queried with the controller Python because target Python has no pip")
        index_urls = request.package_index_urls or self._configured_package_indexes(
            request.python_executable,
            timeout,
            errors,
        )
        if not index_urls:
            index_urls = (PYPI_SIMPLE,)
        elif PYPI_SIMPLE not in index_urls:
            index_urls = (*index_urls, PYPI_SIMPLE)
        rows: list[PackageIndexFacts] = []
        preferred_versions = {
            "torch": python.torch_version,
        }
        # Candidate closure attempts are separate target-Python processes, but
        # their immutable index pages and metadata can be shared safely within
        # one qualification request. The cache is ephemeral and scoped to this
        # request, so it cannot turn stale network content into persisted fact.
        with tempfile.TemporaryDirectory(prefix="research-platform-qualification-") as raw_cache_dir:
            cache_dir = Path(raw_cache_dir)
            for package in sorted(packages):
                for index_url in index_urls:
                    rows.append(
                        self._index(
                            index_python,
                            package,
                            index_url,
                            timeout,
                            preferred_versions=preferred_versions,
                            cache_dir=cache_dir,
                        )
                    )
            if "sglang" in packages:
                for channel in self._kernel_channels(cuda):
                    rows.append(
                        self._index(
                            index_python,
                            "sglang-kernel",
                            _SGLANG_KERNEL_INDEX.format(channel=channel),
                            timeout,
                            preferred_versions={},
                            cache_dir=cache_dir,
                        )
                    )
        return tuple(rows)

    def _configured_package_indexes(
        self,
        executable: Path,
        timeout: float,
        errors: list[str],
    ) -> tuple[str, ...]:
        code, out, _ = self._run((str(executable), "-m", "pip", "config", "list"), timeout)
        if code != 0:
            errors.append("selected Python pip configuration could not be observed")
            return ()
        return self._parse_package_index_urls(out)

    def _index(
        self,
        python: Path,
        package: str,
        index_url: str,
        timeout: float,
        *,
        preferred_versions: dict[str, str | None] | None = None,
        cache_dir: Path | None = None,
    ) -> PackageIndexFacts:
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
        snapshot = self._simple_index_snapshot(
            python,
            package,
            index_url,
            available,
            timeout,
            preferred_versions=preferred_versions,
            cache_dir=cache_dir,
        )
        if (
            snapshot is not None
            and not bool(snapshot.get("dependency_closure_complete"))
            and preferred_versions
            and package in {"vllm", "sglang"}
        ):
            candidate_versions = tuple(
                str(version) for version in available[:_MAX_ROOT_CANDIDATE_ATTEMPTS]
            )
            screening = self._simple_index_snapshot(
                python,
                package,
                index_url,
                available,
                timeout,
                preferred_versions=preferred_versions,
                root_candidates=candidate_versions,
                cache_dir=cache_dir,
            )
            compatible_versions = tuple(
                str(item["version"])
                for item in screening.get("root_candidates", ())
                if bool(item.get("compatible"))
            )
            attempted: list[str] = []
            for version in compatible_versions:
                if str(version) == str(snapshot.get("selected_version")):
                    continue
                attempted.append(str(version))
                alternative = self._simple_index_snapshot(
                    python,
                    package,
                    index_url,
                    available,
                    timeout,
                    preferred_versions=preferred_versions,
                    root_version=str(version),
                    cache_dir=cache_dir,
                )
                if alternative is not None and alternative.get("dependency_closure_complete"):
                    snapshot = alternative
                    break
            else:
                rejected_roots = tuple(
                    f"{item.get('version')}: {item.get('error')}"
                    for item in screening.get("root_candidates", ())
                    if not bool(item.get("compatible")) and item.get("error")
                )
                detail = str(snapshot.get("dependency_closure_error") or "incompatible dependency closure")
                if rejected_roots:
                    detail = detail + "; root screen: " + " | ".join(rejected_roots[:4])
                snapshot["dependency_closure_error"] = (
                    f"no complete {package} candidate after root-screening "
                    f"{len(candidate_versions)} versions and resolving "
                    f"{len(attempted)} root-compatible closures; latest failure: {detail}"
                )
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
        *,
        preferred_versions: dict[str, str | None] | None = None,
        root_version: str | None = None,
        root_candidates: tuple[str, ...] = (),
        cache_dir: Path | None = None,
    ) -> dict[str, object] | None:
        return self._index_snapshot.capture(
            python,
            package,
            index_url,
            available_versions,
            timeout,
            fallback_index=PYPI_SIMPLE,
            preferred_versions=preferred_versions,
            root_version=root_version,
            root_candidates=root_candidates,
            cache_dir=cache_dir,
        )

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
