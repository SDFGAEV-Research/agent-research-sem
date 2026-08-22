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
    id, and the connection identity fields are checked before any adapter can
    attempt network I/O.
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
        entries.append(
            ServerProfileCatalogEntry(
                server_id,
                prefix,
                configured,
                missing,
            )
        )
    return ServerProfileCatalog(source, tuple(entries), environ)


__all__ = ["build_server_profile_catalog"]
