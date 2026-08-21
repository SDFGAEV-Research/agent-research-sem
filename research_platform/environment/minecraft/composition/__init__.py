"""Composition roots for binding MC contracts to concrete platform seams."""

from .participant_runtime import MinecraftParticipantRuntimeAdapter, compose_minecraft_participant_endpoint
from .environment import MinecraftEnvironmentAssembly, compose_minecraft_environment
from .branch_runtime import (
    MinecraftBranchEnvironmentFactoryPort,
    MinecraftBranchRuntimeBinding,
    MinecraftBranchRuntimeError,
    MinecraftBranchRuntimeFactory,
)
from .server_service import (
    MinecraftServerServiceController,
    MinecraftServerServiceError,
    MinecraftServerServiceFactory,
    MinecraftServerServiceFactoryConfig,
    MinecraftTcpReadinessProbe,
    build_server_service_contract,
    compose_minecraft_server_service_runtime,
)
from .diagnostics import (
    MinecraftDiagnosticContext,
    MinecraftFailureMaterializer,
    StructuredMinecraftDiagnostics,
)

__all__ = [
    "MinecraftParticipantRuntimeAdapter",
    "compose_minecraft_participant_endpoint",
    "MinecraftEnvironmentAssembly",
    "MinecraftBranchEnvironmentFactoryPort",
    "MinecraftBranchRuntimeBinding",
    "MinecraftBranchRuntimeError",
    "MinecraftBranchRuntimeFactory",
    "MinecraftServerServiceController",
    "MinecraftServerServiceError",
    "MinecraftServerServiceFactory",
    "MinecraftServerServiceFactoryConfig",
    "MinecraftTcpReadinessProbe",
    "build_server_service_contract",
    "compose_minecraft_server_service_runtime",
    "compose_minecraft_environment",
    "MinecraftDiagnosticContext",
    "MinecraftFailureMaterializer",
    "StructuredMinecraftDiagnostics",
]
