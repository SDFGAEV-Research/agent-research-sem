"""Server health composition."""

from research_platform.runtime.server.health.api import (
    ServerDiagnosticProjectorPort,
    ServerHealthProbePort,
    ServerRuntimeHealthSpec,
)
from research_platform.runtime.server.health.providers import SSHServerHealthProbe
from research_platform.runtime.server.health.runtime import ServerDiagnosticProjector
from research_platform.runtime.server.lifecycle.api import ServerRemoteProfile


def compose_ssh_server_health() -> ServerHealthProbePort:
    return SSHServerHealthProbe()


def compose_server_diagnostic_projector() -> ServerDiagnosticProjectorPort:
    return ServerDiagnosticProjector()


def compose_server_runtime_health_spec(profile: ServerRemoteProfile) -> ServerRuntimeHealthSpec:
    """Bind a server's frozen remote profile to the generic health contract."""

    return ServerRuntimeHealthSpec(
        platform_root=profile.platform_root,
        release_root=profile.release_root,
        remote_home=profile.remote_home,
        python_executable=profile.python_executable,
        python_binary_sha256=profile.python_binary_sha256,
        python_packages_sha256=profile.python_packages_sha256,
        node_executable=profile.node_executable,
        node_binary_sha256=profile.node_binary_sha256,
        java_executable=profile.java_executable,
        java_binary_sha256=profile.java_binary_sha256,
        platform_management_executable=profile.platform_management_executable,
        platform_management_binary_sha256=profile.platform_management_binary_sha256,
        tmux_executable=profile.tmux_executable,
        sha256sum_executable=profile.sha256sum_executable,
        tmux_binary_sha256=profile.tmux_binary_sha256,
    )


__all__ = [
    "compose_server_diagnostic_projector",
    "compose_server_runtime_health_spec",
    "compose_ssh_server_health",
]
