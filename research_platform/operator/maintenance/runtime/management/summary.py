from __future__ import annotations

from research_platform.resource.directory.api import ManagedDirectoryKind

from .context import ManagementCommandContext

GROUP = "summary"


def register(groups) -> None:
    groups.add_parser(GROUP)


def dispatch(args, context: ManagementCommandContext):
    del args
    directories = context.directories
    return {
        "directories": {
            kind.value: directories.inspection.overview(kind)
            for kind in (
                ManagedDirectoryKind.MODEL_ARTIFACTS,
                ManagedDirectoryKind.PYTHON_ENVIRONMENTS,
                ManagedDirectoryKind.LOGS,
                ManagedDirectoryKind.CACHE,
                ManagedDirectoryKind.WORKSPACES,
            )
        },
        "environments": context.environments.lifecycle.list(),
        "models": {
            "inventory": context.models.resources.snapshot(),
            "storage_pools": context.models.assets.storage_pools(),
        },
    }


__all__ = ["GROUP", "dispatch", "register"]
