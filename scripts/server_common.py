from __future__ import annotations

from collections.abc import Mapping

from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.runtime.host.composition import compose_local_host
from research_platform.runtime.server.composition import (
    ServerManagementComposition,
    compose_environment_server,
    load_server_management_environment,
)
from research_platform.runtime.server.identity.composition import compose_environment_server_identity


def compose_server_from_environment(
    server_id: str,
    *,
    environ: Mapping[str, str],
) -> ServerManagementComposition:
    """Compose the outer host/platform route once, then bind runtime/server."""

    meta = build_in_memory_platform_meta()
    host = compose_local_host(planner=meta.capability_composition)
    identity = compose_environment_server_identity(
        operating_system=host.operating_system,
        host_operating_system_offer=host.operating_system_offer,
        planner=meta.capability_composition,
    )
    return compose_environment_server(
        server_id,
        environ=environ,
        identity=identity,
    )


def compose_script_server(
    server_id: str,
    *,
    profile_file: str | None,
) -> tuple[Mapping[str, str], ServerManagementComposition]:
    environ = load_server_management_environment(profile_file)
    return environ, compose_server_from_environment(server_id, environ=environ)


def load_script_environment(profile_file: str | None) -> Mapping[str, str]:
    return load_server_management_environment(profile_file)


__all__ = [
    "compose_script_server",
    "compose_server_from_environment",
    "load_script_environment",
]
