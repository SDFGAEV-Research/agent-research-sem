from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from research_platform.resource.directory.api import DirectoryLayout, DirectoryLayoutPort, DirectoryManagementAuthorities
from research_platform.resource.directory.runtime import build_local_directory_authorities
from research_platform.model.api import ModelAuthorities
from research_platform.model.deployment.api import ModelDeploymentLogs
from research_platform.model.asset.providers import HuggingFaceCliModelSource
from research_platform.model.asset.runtime import LocalModelAssetStorage, ModelAssetManager, ModelAssetRegistry
from research_platform.model.composition import DeploymentModelAssetReferences
from research_platform.model.assignment.runtime import ModelAssignmentManager
from research_platform.model.deployment.runtime import (
    AppliedModelDeploymentStore,
    FileModelControllerStateStore,
    ModelDesiredStateController,
    ModelDeploymentCatalog,
    ModelDeploymentLogReader,
    ModelDeploymentRegistry,
    ModelDeploymentRuntime,
    ModelLaunchMaterializer,
    ModelFleetRuntime,
    ModelResourceView,
)
from research_platform.resource.compute.providers import NvidiaSmiGpuRuntimeObserver
from research_platform.environment.python.api import PythonEnvironmentAuthorities
from research_platform.environment.catalog.api import ExecutionEnvironmentCatalogPort
from research_platform.environment.catalog.runtime import ExecutionEnvironmentCatalog
from research_platform.scope.api import ScopeRegistryPort
from research_platform.scope.runtime import InMemoryScopeRegistry
from research_platform.environment.python.runtime import (
    CondaEnvironmentBackend,
    build_python_environment_authorities,
    SubprocessEnvironmentCommandRunner,
    VenvEnvironmentBackend,
)
from research_platform.runtime.service.api import ServiceLaunchContract
from research_platform.runtime.service.runtime.capture_paths import DirectoryCapturePathProvider
from research_platform.runtime.service.runtime.environment import MaterializedServiceEnvironment, StaticServiceEnvironmentProvider
from research_platform.runtime.service.runtime.linux_backend import LinuxProcessBackend
from research_platform.runtime.service.runtime.process_adapter import LocalServiceProcessAdapter
from research_platform.runtime.service.runtime.readiness import HttpEndpointReadinessProbe, ProcessAliveReadinessProbe
from research_platform.runtime.service.runtime.runtime_endpoint import ExactServiceRuntimeEndpoint
from research_platform.runtime.service.runtime.start_intent_store import DirectoryServiceStartIntentStore
from research_platform.runtime.service.runtime.state_storage import FileServiceStateStore

from research_platform.runtime.service.composition import build_service_supervisor


@dataclass(frozen=True, slots=True)
class ManagementPlaneAuthorities:
    scopes: ScopeRegistryPort
    directories: DirectoryManagementAuthorities
    execution_environments: ExecutionEnvironmentCatalogPort
    python_environments: PythonEnvironmentAuthorities
    models: ModelAuthorities


class LocalModelServiceRuntimeFactory:
    """Composition-only factory for many independently managed local model services."""

    def __init__(self, directories: DirectoryLayoutPort) -> None:
        self._directories = directories
        self._state_root = directories.layout.state / "model-services"
        self._intent_root = directories.layout.runtime / "model-service-start-intents"
        self._capture_root = directories.layout.logs / "model-services"

    def open(
        self,
        contract: ServiceLaunchContract,
        *,
        environment: tuple[tuple[str, str], ...],
        readiness_url: str | None,
    ) -> ExactServiceRuntimeEndpoint:
        service_key = self._safe(contract.service_id)
        materialized = MaterializedServiceEnvironment(
            variables=environment,
            evidence_ref=f"model-serving-env:{contract.environment_digest}",
        )
        provider = StaticServiceEnvironmentProvider((materialized,))
        backend = LinuxProcessBackend()
        readiness = (
            HttpEndpointReadinessProbe(readiness_url)
            if readiness_url
            else ProcessAliveReadinessProbe()
        )
        adapter = LocalServiceProcessAdapter(
            provider,
            DirectoryCapturePathProvider(self._capture_root),
            backend,
            readiness,
        )
        contract_key = contract.digest()
        state = FileServiceStateStore(self._state_root / service_key / contract_key / "state.json")
        intents = DirectoryServiceStartIntentStore(self._intent_root / service_key / contract_key)
        return ExactServiceRuntimeEndpoint(build_service_supervisor(state, intents, adapter))


    def logs(self, contract: ServiceLaunchContract, *, deployment_id: str) -> ModelDeploymentLogs:
        paths = DirectoryCapturePathProvider(self._capture_root).paths(contract)
        return ModelDeploymentLogs(deployment_id, paths.stdout_path, paths.stderr_path)

    @staticmethod
    def _safe(value: str) -> str:
        return value.replace("/", "_").replace("\\", "_")


def build_local_management_plane(
    layout: DirectoryLayout,
    *,
    base_service_environment: tuple[tuple[str, str], ...] = (),
    huggingface_cli: str = "hf",
    model_storage_pools: Mapping[str, Path] | None = None,
) -> ManagementPlaneAuthorities:
    scopes = InMemoryScopeRegistry()
    directories = build_local_directory_authorities(layout)
    directory_layout = directories.layout
    runner = SubprocessEnvironmentCommandRunner()
    pip_cache = directory_layout.layout.cache / "pip"
    conda_cache = directory_layout.layout.cache / "conda-packages"
    environments = build_python_environment_authorities(
        directory_layout,
        (
            VenvEnvironmentBackend(runner, pip_cache=pip_cache),
            CondaEnvironmentBackend(
                runner, executable="conda", backend_id="conda",
                conda_package_cache=conda_cache, pip_cache=pip_cache,
            ),
            CondaEnvironmentBackend(
                runner, executable="mamba", backend_id="mamba",
                conda_package_cache=conda_cache, pip_cache=pip_cache,
            ),
        ),
        runner,
    )
    execution_environments = ExecutionEnvironmentCatalog(scopes)
    asset_registry = ModelAssetRegistry(directory_layout)
    deployment_registry = ModelDeploymentRegistry(directory_layout)
    applied_store = AppliedModelDeploymentStore(directory_layout)
    asset_storage = LocalModelAssetStorage(directory_layout, additional_pools=model_storage_pools)
    deployment_catalog = ModelDeploymentCatalog(asset_registry, deployment_registry, environments.lifecycle)
    assets = ModelAssetManager(
        asset_registry,
        DeploymentModelAssetReferences(deployment_catalog),
        asset_storage,
        (HuggingFaceCliModelSource(
            asset_storage, executable=huggingface_cli, cache_root=directory_layout.layout.cache / "huggingface"
        ),),
    )
    assignments = ModelAssignmentManager(scopes)
    service_factory = LocalModelServiceRuntimeFactory(directory_layout)
    materializer = ModelLaunchMaterializer(
        assets, environments.lifecycle, base_environment=base_service_environment
    )
    deployment_runtime = ModelDeploymentRuntime(
        applied_store, deployment_catalog, materializer, service_factory
    )
    fleet = ModelFleetRuntime(deployment_catalog, deployment_runtime)
    deployment_logs = ModelDeploymentLogReader(
        applied_store, deployment_catalog, materializer, service_factory
    )
    resources = ModelResourceView(
        assets, deployment_catalog, fleet, NvidiaSmiGpuRuntimeObserver()
    )
    controller = ModelDesiredStateController(
        fleet,
        FileModelControllerStateStore(directory_layout.layout.state / "model" / "deployments" / "controller.json"),
    )
    models = ModelAuthorities(
        assets, assignments, deployment_catalog, deployment_runtime, fleet, deployment_logs, resources, controller
    )
    return ManagementPlaneAuthorities(scopes, directories, execution_environments, environments, models)


__all__ = ["LocalModelServiceRuntimeFactory", "ManagementPlaneAuthorities", "build_local_management_plane"]
