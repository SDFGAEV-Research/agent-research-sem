from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from research_platform.scope.api import ScopeIdentity


class PythonEnvironmentState(StrEnum):
    REGISTERED = "registered"
    READY = "ready"
    MISSING = "missing"


class PythonEnvironmentOwnership(StrEnum):
    MANAGED = "managed"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class PythonEnvironmentSpec:
    environment_id: str
    scope: ScopeIdentity
    backend: str = "venv"
    python_executable: str = "python3"
    python_version: str | None = None
    description: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ManagedPythonEnvironment:
    environment_id: str
    scope: ScopeIdentity
    backend: str
    root: Path
    python_path: Path
    state: PythonEnvironmentState
    ownership: PythonEnvironmentOwnership
    description: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EnvironmentCommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class InstalledPythonPackage:
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class PythonEnvironmentCloneResult:
    source_environment_id: str
    environment: ManagedPythonEnvironment
    requirements_count: int
    install_result: EnvironmentCommandResult | None = None


__all__ = [
    "EnvironmentCommandResult",
    "InstalledPythonPackage",
    "ManagedPythonEnvironment",
    "PythonEnvironmentCloneResult",
    "PythonEnvironmentOwnership",
    "PythonEnvironmentSpec",
    "PythonEnvironmentState",
]
