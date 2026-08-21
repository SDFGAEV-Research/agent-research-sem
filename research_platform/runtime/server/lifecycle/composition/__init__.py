"""Server lifecycle composition."""

from research_platform.runtime.server.identity.api import (
    ServerConnectionPort,
    ServerFileTransferPort,
)
from research_platform.runtime.server.lifecycle.api import ServerReleaseDeploymentPort
from research_platform.runtime.server.lifecycle.providers import SSHServerReleasePublisher
from research_platform.runtime.server.lifecycle.api import ServerRemoteProfile
from research_platform.runtime.session.providers import SSHRemoteTmuxSessionControl


def compose_ssh_server_release_publisher(
    *,
    connection: ServerConnectionPort,
    transfer: ServerFileTransferPort,
    python_executable: str,
) -> ServerReleaseDeploymentPort:
    return SSHServerReleasePublisher(connection, transfer, python_executable=python_executable)


def compose_ssh_server_session_control(
    *,
    connection: ServerConnectionPort,
    profile: ServerRemoteProfile,
    interactive: bool,
) -> SSHRemoteTmuxSessionControl:
    """Compose the server-bound session backend at the lifecycle boundary."""

    return SSHRemoteTmuxSessionControl(
        connection,
        tmux_executable=profile.tmux_executable,
        binary_identity_digest=profile.tmux_binary_sha256,
        server_label=profile.tmux_server_label,
        config_file=profile.tmux_config_file,
        socket_directory=profile.tmux_socket_directory,
        remote_env_executable=profile.remote_env_executable,
        sha256sum_executable=profile.sha256sum_executable,
        session_environment=profile.session_environment,
        interactive=interactive,
    )


__all__ = ["compose_ssh_server_release_publisher", "compose_ssh_server_session_control"]
