"""Server lifecycle composition."""

from research_platform.runtime.server.identity.api import (
    ServerConnectionPort,
    ServerFileTransferPort,
)
from research_platform.runtime.server.lifecycle.api import ServerReleaseDeploymentPort
from research_platform.runtime.server.lifecycle.providers import SSHServerReleasePublisher


def compose_ssh_server_release_publisher(
    *,
    connection: ServerConnectionPort,
    transfer: ServerFileTransferPort,
) -> ServerReleaseDeploymentPort:
    return SSHServerReleasePublisher(connection, transfer)


__all__ = ["compose_ssh_server_release_publisher"]
