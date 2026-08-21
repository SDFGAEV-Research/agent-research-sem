from __future__ import annotations

from pathlib import Path
import shutil

from research_platform.resource.directory.api import DirectoryLayoutPort, ManagedDirectoryKind
from research_platform.environment.python.api import (
    ManagedPythonEnvironment,
    PythonEnvironmentBackend,
    PythonEnvironmentOwnership,
    PythonEnvironmentSpec,
    PythonEnvironmentState,
)

from .registry import PythonEnvironmentRegistry


class PythonEnvironmentLifecycle:
    """Create/register/remove authority plus environment lookup."""

    def __init__(
        self,
        directories: DirectoryLayoutPort,
        registry: PythonEnvironmentRegistry,
        backends: tuple[PythonEnvironmentBackend, ...],
    ) -> None:
        self._root = directories.root(ManagedDirectoryKind.PYTHON_ENVIRONMENTS)
        self._registry = registry
        self._backends = {backend.backend_id: backend for backend in backends}
        if len(self._backends) != len(backends):
            raise ValueError("duplicate Python environment backend")

    def create(self, spec: PythonEnvironmentSpec) -> ManagedPythonEnvironment:
        self._validate_id(spec.environment_id)
        backend = self._backend(spec.backend)
        root = self._root / spec.environment_id
        if root.exists() and any(root.iterdir()):
            raise FileExistsError(f"Python environment already exists: {spec.environment_id}")
        python_path = backend.create(root, spec)
        return self._registry.put(
            ManagedPythonEnvironment(
                spec.environment_id,
                spec.scope,
                spec.backend,
                root,
                python_path,
                PythonEnvironmentState.READY,
                PythonEnvironmentOwnership.MANAGED,
                spec.description,
                self._normalize_tags(spec.tags),
                spec.specification_digest,
            )
        )

    def register_existing(self, spec: PythonEnvironmentSpec, root: Path) -> ManagedPythonEnvironment:
        self._validate_id(spec.environment_id)
        backend = self._backend(spec.backend)
        resolved = root.expanduser().resolve()
        python_path = backend.python_path(resolved)
        state = PythonEnvironmentState.READY if python_path.exists() else PythonEnvironmentState.MISSING
        return self._registry.put(
            ManagedPythonEnvironment(
                spec.environment_id,
                spec.scope,
                spec.backend,
                resolved,
                python_path,
                state,
                PythonEnvironmentOwnership.EXTERNAL,
                spec.description,
                self._normalize_tags(spec.tags),
                spec.specification_digest,
            )
        )

    def get(self, environment_id: str) -> ManagedPythonEnvironment:
        return self._registry.get(environment_id)

    def migrate_legacy(
        self,
        environment_id: str,
        *,
        python_executable: str,
        python_version: str,
    ) -> ManagedPythonEnvironment:
        return self._registry.migrate_legacy(
            environment_id,
            python_executable=python_executable,
            python_version=python_version,
        )

    def list(self, *, tags: tuple[str, ...] = ()) -> tuple[ManagedPythonEnvironment, ...]:
        required = set(self._normalize_tags(tags))
        values = self._registry.all()
        if not required:
            return values
        return tuple(value for value in values if required.issubset(value.tags))

    def backends(self) -> tuple[str, ...]:
        return tuple(sorted(self._backends))

    def remove(self, environment_id: str) -> bool:
        value = self.get(environment_id)
        managed_root = self._root / environment_id
        if value.ownership is PythonEnvironmentOwnership.MANAGED and managed_root.exists():
            shutil.rmtree(managed_root)
        return self._registry.remove(environment_id)

    def backend(self, backend_id: str) -> PythonEnvironmentBackend:
        return self._backend(backend_id)

    def _backend(self, backend_id: str) -> PythonEnvironmentBackend:
        try:
            return self._backends[backend_id]
        except KeyError as exc:
            raise KeyError(f"unknown Python environment backend: {backend_id}") from exc

    @staticmethod
    def _normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
        values = tuple(sorted({str(tag).strip() for tag in tags if str(tag).strip()}))
        if any("/" in tag or "\\" in tag for tag in values):
            raise ValueError("Python environment tags cannot contain path separators")
        return values

    @staticmethod
    def _validate_id(value: str) -> None:
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("invalid Python environment id")


__all__ = ["PythonEnvironmentLifecycle"]
