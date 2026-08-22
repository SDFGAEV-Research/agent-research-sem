from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from research_platform.platform.kernel import canonical_digest
from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.runtime.host.composition import compose_local_host
from research_platform.runtime.server.composition import (
    ServerManagementComposition,
    compose_environment_server,
    load_server_management_environment,
)
from research_platform.runtime.server.health.api import ServerRuntimeHealthSpec
from research_platform.runtime.server.health.composition import compose_server_runtime_health_spec
from research_platform.runtime.server.identity.composition import compose_environment_server_identity
from research_platform.runtime.server.identity.api import ServerProfileCatalog
from research_platform.runtime.server.identity.providers import (
    build_server_profile_catalog,
)
from research_platform.runtime.server.lifecycle.composition import compose_ssh_server_session_control
from research_platform.runtime.session.api import PersistentSessionSpec
from research_platform.runtime.session.api import PersistentSessionControlPort
from research_platform.runtime.session.runtime import (
    BoundPersistentSessionStatusProbe,
    DirectoryPersistentSessionBindingStore,
    PersistentSessionManager,
)


@dataclass(frozen=True, slots=True)
class ServerOperatorSessionComposition:
    """Shared entrypoint composition for the profile-bound operator session."""

    server: ServerManagementComposition
    control: PersistentSessionControlPort
    manager: PersistentSessionManager
    spec: PersistentSessionSpec
    bindings: DirectoryPersistentSessionBindingStore


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
    catalog = build_server_profile_catalog(environ, source=profile_file or "environment")
    entry = catalog.entry(server_id)
    if not entry.composition_ready:
        missing = ", ".join(entry.missing_identity_fields)
        raise ValueError(f"server profile is incomplete for {server_id}: missing {missing}")
    selected = catalog.environment_for(server_id)
    return selected, compose_server_from_environment(server_id, environ=selected)


def load_script_environment(profile_file: str | None) -> Mapping[str, str]:
    return load_server_management_environment(profile_file)


def compose_script_server_catalog(
    profile_file: str | None,
) -> tuple[Mapping[str, str], ServerProfileCatalog]:
    environ = load_script_environment(profile_file)
    source = profile_file or "environment"
    return environ, build_server_profile_catalog(environ, source=source)


def server_health_spec(server: ServerManagementComposition) -> ServerRuntimeHealthSpec:
    return compose_server_runtime_health_spec(server.remote_profile)


def compose_server_operator_session(
    server: ServerManagementComposition,
    *,
    interactive: bool,
    session_name: str | None = None,
) -> ServerOperatorSessionComposition:
    """Materialize the one operator-session binding used by all server tools."""

    profile = server.remote_profile
    selected_name = session_name or profile.session_name
    control = compose_ssh_server_session_control(
        connection=server.connection,
        profile=profile,
        interactive=interactive,
    )
    profile.local_binding_root.mkdir(parents=True, exist_ok=True)
    bindings = DirectoryPersistentSessionBindingStore(profile.local_binding_root)
    manager = PersistentSessionManager(control, bindings)
    spec = PersistentSessionSpec(
        session_name=selected_name,
        command_argv=(profile.operator_shell, *profile.operator_shell_args),
        cwd=profile.operator_cwd,
        control_id=f"operator-shell:{profile.server_id}",
        runtime_manifest_digest=canonical_digest(
            {
                "server_profile_digest": server.profile_digest,
                "server_id": profile.server_id,
                "platform_root": profile.platform_root,
                "operator_cwd": profile.operator_cwd,
                "operator_shell": profile.operator_shell,
                "operator_shell_args": profile.operator_shell_args,
                "remote_path": profile.remote_path,
                "session_environment": profile.session_environment,
            }
        ),
        process_environment=profile.session_environment,
    )
    return ServerOperatorSessionComposition(server, control, manager, spec, bindings)


def compose_server_session_observation(
    composition: ServerOperatorSessionComposition,
):
    return BoundPersistentSessionStatusProbe(
        composition.control,
        composition.bindings,
        composition.spec.session_name,
        expected_spec=composition.spec,
    ).observe()


__all__ = [
    "compose_script_server",
    "compose_script_server_catalog",
    "compose_server_operator_session",
    "compose_server_from_environment",
    "compose_server_session_observation",
    "load_script_environment",
    "server_health_spec",
    "ServerOperatorSessionComposition",
]
