"""Composition roots for binding MC contracts to concrete platform seams."""

from .participant_runtime import MinecraftParticipantRuntimeAdapter
from .environment import MinecraftEnvironmentAssembly, compose_minecraft_environment
from .server_service import (
    MinecraftServerServiceController,
    MinecraftServerServiceError,
    MinecraftTcpReadinessProbe,
    build_server_service_contract,
)
from .diagnostics import (
    MinecraftDiagnosticContext,
    MinecraftFailureMaterializer,
    StructuredMinecraftDiagnostics,
)

__all__ = [
    "MinecraftParticipantRuntimeAdapter",
    "MinecraftEnvironmentAssembly",
    "MinecraftServerServiceController",
    "MinecraftServerServiceError",
    "MinecraftTcpReadinessProbe",
    "build_server_service_contract",
    "compose_minecraft_environment",
    "MinecraftDiagnosticContext",
    "MinecraftFailureMaterializer",
    "StructuredMinecraftDiagnostics",
]
