from __future__ import annotations

from dataclasses import dataclass

from research_platform.resource.directory.api import DirectoryManagementAuthorities
from research_platform.model.api import ModelAuthorities
from research_platform.environment.python.api import PythonEnvironmentAuthorities
from research_platform.environment.catalog.api import ExecutionEnvironmentCatalogPort
from research_platform.scope.api import ScopeRegistryPort


@dataclass(frozen=True, slots=True)
class ManagementCommandContext:
    scopes: ScopeRegistryPort
    directories: DirectoryManagementAuthorities
    execution_environments: ExecutionEnvironmentCatalogPort
    environments: PythonEnvironmentAuthorities
    models: ModelAuthorities


__all__ = ["ManagementCommandContext"]
