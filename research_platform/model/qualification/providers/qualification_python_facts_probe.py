"""Target-Python facts for deployment qualification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from research_platform.model.qualification.api import PythonRuntimeFacts

CommandRun = Callable[[tuple[str, ...], float], tuple[int, str, str]]


class PythonFactsProbe:
    """Capture read-only interpreter and installed-runtime facts."""

    def __init__(self, run: CommandRun) -> None:
        self._run = run
    def capture(self, executable: Path, timeout: float) -> tuple[PythonRuntimeFacts, list[str]]:
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

__all__ = ["PythonFactsProbe"]
