from __future__ import annotations

import shutil
from pathlib import Path
import subprocess

from research_platform.model.asset.api import (
    ModelAcquisitionReceipt,
    ModelAssetStoragePort,
    ModelSourceSpec,
)


class HuggingFaceCliModelSource:
    """Explicit operator-triggered Hugging Face download backend."""

    backend_id = "huggingface"

    def __init__(
        self, storage: ModelAssetStoragePort, *, executable: str = "hf", cache_root: Path | None = None
    ) -> None:
        self._storage = storage
        self._executable = executable
        self._cache_root = cache_root
        if self._cache_root is not None:
            self._cache_root.mkdir(parents=True, exist_ok=True)

    def acquire(self, model_id: str, spec: ModelSourceSpec) -> ModelAcquisitionReceipt:
        destination = self._storage.target(model_id, pool_id=spec.storage_pool)
        if destination.is_symlink():
            raise FileExistsError(f"model target is a symlink: {model_id}")
        if destination.exists() and not spec.resume:
            raise FileExistsError(f"model target already exists: {model_id}")
        executable = shutil.which(self._executable)
        if executable is None:
            raise FileNotFoundError(self._executable)
        argv = [executable, "download", spec.source, "--local-dir", str(destination)]
        if self._cache_root is not None:
            argv.extend(("--cache-dir", str(self._cache_root)))
        if spec.revision:
            argv.extend(("--revision", spec.revision))
        for pattern in spec.include:
            argv.extend(("--include", pattern))
        for pattern in spec.exclude:
            argv.extend(("--exclude", pattern))
        completed = subprocess.run(tuple(argv), check=False)
        if completed.returncode != 0:
            raise RuntimeError("model source acquisition failed")
        return ModelAcquisitionReceipt(model_id, self.backend_id, spec.source, destination, spec.revision, spec.storage_pool)


__all__ = ["HuggingFaceCliModelSource"]
