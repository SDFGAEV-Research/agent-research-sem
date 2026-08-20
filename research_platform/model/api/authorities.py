from __future__ import annotations
from dataclasses import dataclass
from research_platform.model.asset.api import ModelAssetManagementPort
from research_platform.model.assignment.api import ModelAssignmentPort
from research_platform.model.deployment.api import (
    ModelDeploymentCatalogPort, ModelDeploymentLogPort, ModelDeploymentRuntimePort, ModelFleetRuntimePort,
    ModelReconcileControllerPort, ModelResourceViewPort,
)

@dataclass(frozen=True, slots=True)
class ModelAuthorities:
    assets: ModelAssetManagementPort
    assignments: ModelAssignmentPort
    deployment_catalog: ModelDeploymentCatalogPort
    deployment_runtime: ModelDeploymentRuntimePort
    fleet: ModelFleetRuntimePort
    deployment_logs: ModelDeploymentLogPort
    resources: ModelResourceViewPort
    controller: ModelReconcileControllerPort

__all__ = ["ModelAuthorities"]
