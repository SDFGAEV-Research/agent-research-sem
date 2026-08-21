from research_platform.runtime.host.providers import LocalOperatingSystemRoute
from research_platform.runtime.server.identity.providers import EnvironmentSSHServerConnectionFactory


def build_environment_server_connection(server_id: str):
    return EnvironmentSSHServerConnectionFactory(
        LocalOperatingSystemRoute()
    ).from_environment(server_id)


__all__ = ["build_environment_server_connection"]
