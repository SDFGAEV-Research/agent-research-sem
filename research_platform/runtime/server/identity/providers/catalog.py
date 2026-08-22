from __future__ import annotations

from collections.abc import Mapping
import re

from ..api import (
    ServerProfileCatalog,
    ServerProfileCatalogEntry,
    ServerProfileCatalogError,
    server_environment_prefix,
)


_CATALOG_IDS_KEY = "RP_SERVER_CATALOG_IDS"
_PROFILE_FILE_KEY = "RP_SERVER_PROFILE_FILE"
_IDENTITY_FIELDS = ("HOST", "PORT", "USER")
# These are the fields consumed by ServerRemoteProfile. Keeping the schema at
# the catalog boundary lets offline diagnostics report all missing data before
# any adapter attempts network I/O. RELEASE_ROOT has a deliberate default.
_RUNTIME_FIELDS = (
    "PLATFORM_ROOT",
    "OPERATOR_CWD",
    "REPOSITORY_ROOT",
    "OPERATOR_SHELL",
    "OPERATOR_SHELL_ARGS",
    "REMOTE_ENV",
    "SHA256SUM",
    "PYTHON",
    "PYTHON_SHA256",
    "PYTHON_PACKAGES_SHA256",
    "NODE",
    "NODE_SHA256",
    "JAVA",
    "JAVA_SHA256",
    "PLATFORM_MANAGE",
    "PLATFORM_MANAGE_SHA256",
    "TMUX",
    "TMUX_SHA256",
    "TMUX_SERVER_LABEL",
    "TMUX_CONFIG",
    "TMUX_SOCKET_DIRECTORY",
    "SESSION_NAME",
    "LOCAL_BINDING_ROOT",
    "REMOTE_HOME",
    "REMOTE_PATH",
    "TERM",
)
_SERVER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def build_server_profile_catalog(
    environ: Mapping[str, str],
    *,
    source: str = "environment",
) -> ServerProfileCatalog:
    """Build the one immutable membership projection for a server profile.

    Membership is explicit.  Inferring ``sem-ubuntu`` from ``SEM_UBUNTU``
    would make underscores and hyphens ambiguous and would turn a typo into a
    different host.  Every ``RP_SERVER_<ID>_*`` key must belong to a declared
    id, and connection/runtime fields are checked before any adapter can
    attempt network I/O. Remote existence remains the health system's job.
    """

    raw_ids = str(environ.get(_CATALOG_IDS_KEY, "")).strip()
    if not raw_ids:
        raise ServerProfileCatalogError(
            f"{_CATALOG_IDS_KEY} is required; declare comma-separated logical server ids"
        )
    server_ids = tuple(part.strip() for part in raw_ids.split(","))
    if any(not _SERVER_ID_RE.fullmatch(server_id) for server_id in server_ids):
        raise ServerProfileCatalogError(
            f"{_CATALOG_IDS_KEY} contains an unsafe or empty server id"
        )
    if len(server_ids) != len(set(server_ids)):
        raise ServerProfileCatalogError(f"{_CATALOG_IDS_KEY} contains duplicate server ids")

    prefixes = {server_id: server_environment_prefix(server_id) for server_id in server_ids}
    allowed_control_keys = {_CATALOG_IDS_KEY, _PROFILE_FILE_KEY}
    for key in environ:
        if not key.startswith("RP_SERVER_") or key in allowed_control_keys:
            continue
        if not any(key.startswith(prefix + "_") for prefix in prefixes.values()):
            raise ServerProfileCatalogError(
                f"server profile key is outside declared catalog membership: {key}"
            )

    entries: list[ServerProfileCatalogEntry] = []
    for server_id in server_ids:
        prefix = prefixes[server_id]
        configured = tuple(
            sorted(
                key[len(prefix) + 1 :]
                for key in environ
                if key.startswith(prefix + "_")
            )
        )
        missing = tuple(
            field
            for field in _IDENTITY_FIELDS
            if not str(environ.get(f"{prefix}_{field}", "")).strip()
        )
        missing_runtime = tuple(
            field
            for field in _RUNTIME_FIELDS
            if not str(environ.get(f"{prefix}_{field}", "")).strip()
        )
        entries.append(
            ServerProfileCatalogEntry(
                server_id,
                prefix,
                configured,
                missing,
                missing_runtime,
            )
        )
    return ServerProfileCatalog(source, tuple(entries), environ)


__all__ = ["build_server_profile_catalog"]
