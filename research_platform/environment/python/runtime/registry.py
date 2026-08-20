from __future__ import annotations

import json
from pathlib import Path

from research_platform.resource.directory.api import DirectoryLayoutPort, ManagedDirectoryKind
from research_platform.environment.python.api import (
    ManagedPythonEnvironment,
    PythonEnvironmentOwnership,
    PythonEnvironmentState,
)
from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes
from research_platform.scope.api import scope_from_data, scope_to_data


class PythonEnvironmentRegistry:
    """Authoritative operator metadata for registered Python environments."""

    def __init__(self, directories: DirectoryLayoutPort) -> None:
        self._root = directories.root(ManagedDirectoryKind.STATE) / "python-environments"
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, value: ManagedPythonEnvironment) -> ManagedPythonEnvironment:
        self._validate_id(value.environment_id)
        payload = json.dumps(
            {
                "environment_id": value.environment_id,
                "scope": scope_to_data(value.scope),
                "backend": value.backend,
                "root": str(value.root),
                "python_path": str(value.python_path),
                "ownership": value.ownership.value,
                "description": value.description,
                "tags": list(value.tags),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        atomic_replace_bytes(self._root / f"{value.environment_id}.json", payload)
        return value

    def get(self, environment_id: str) -> ManagedPythonEnvironment:
        self._validate_id(environment_id)
        path = self._root / f"{environment_id}.json"
        if not path.exists():
            raise KeyError(environment_id)
        data = json.loads(path.read_text("utf-8"))
        value = ManagedPythonEnvironment(
            environment_id=str(data["environment_id"]),
            scope=scope_from_data(data["scope"]),
            backend=str(data["backend"]),
            root=Path(str(data["root"])),
            python_path=Path(str(data["python_path"])),
            state=PythonEnvironmentState.REGISTERED,
            ownership=PythonEnvironmentOwnership(str(data["ownership"])),
            description=str(data.get("description", "")),
            tags=tuple(str(item) for item in data.get("tags", ())),
        )
        state = PythonEnvironmentState.READY if value.python_path.exists() else PythonEnvironmentState.MISSING
        return ManagedPythonEnvironment(
            value.environment_id,
            value.scope,
            value.backend,
            value.root,
            value.python_path,
            state,
            value.ownership,
            value.description,
            value.tags,
        )

    def all(self) -> tuple[ManagedPythonEnvironment, ...]:
        return tuple(self.get(path.stem) for path in sorted(self._root.glob("*.json")))

    def remove(self, environment_id: str) -> bool:
        self._validate_id(environment_id)
        path = self._root / f"{environment_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    @staticmethod
    def _validate_id(value: str) -> None:
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("invalid Python environment id")


__all__ = ["PythonEnvironmentRegistry"]
