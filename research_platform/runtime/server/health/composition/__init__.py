"""Server health composition."""

from research_platform.runtime.server.health.api import ServerHealthProbePort
from research_platform.runtime.server.health.providers import SSHServerHealthProbe


def compose_ssh_server_health() -> ServerHealthProbePort:
    return SSHServerHealthProbe()


__all__ = ["compose_ssh_server_health"]
