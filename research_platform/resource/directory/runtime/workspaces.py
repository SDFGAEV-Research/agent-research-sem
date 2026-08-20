from __future__ import annotations

import json
import shutil

from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes
from research_platform.resource.directory.api import DirectoryLayoutPort, ManagedDirectoryKind, WorkspaceAllocation
from research_platform.scope.api import ScopeIdentity, scope_from_data, scope_to_data


class LocalWorkspaceManager:
    """Scoped workspace allocation/removal authority."""

    def __init__(self, directories: DirectoryLayoutPort) -> None:
        self._directories = directories

    def _path(self, scope: ScopeIdentity, category: str, workspace_id: str):
        self._validate_name(scope.scope_id, "scope_id")
        return (
            self._directories.root(ManagedDirectoryKind.WORKSPACES)
            / scope.kind.value
            / scope.scope_id
            / category
            / workspace_id
        )

    def allocate_workspace(
        self,
        workspace_id: str,
        *,
        scope: ScopeIdentity,
        category: str = "default",
        owner: str | None = None,
        note: str | None = None,
    ) -> WorkspaceAllocation:
        self._validate_name(workspace_id, "workspace_id")
        self._validate_name(category, "category")
        path = self._path(scope, category, workspace_id)
        path.mkdir(parents=True, exist_ok=True)
        allocation = WorkspaceAllocation(workspace_id, scope, category, path, owner, note)
        payload = json.dumps(
            {
                "workspace_id": allocation.workspace_id,
                "scope": scope_to_data(allocation.scope),
                "category": allocation.category,
                "path": str(allocation.path),
                "owner": allocation.owner,
                "note": allocation.note,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        atomic_replace_bytes(path / ".workspace.json", payload)
        return allocation

    def list_workspaces(self, *, scope: ScopeIdentity | None = None, category: str | None = None) -> tuple[WorkspaceAllocation, ...]:
        root = self._directories.root(ManagedDirectoryKind.WORKSPACES)
        values: list[WorkspaceAllocation] = []
        for metadata in sorted(root.rglob(".workspace.json")):
            decoded = json.loads(metadata.read_text("utf-8"))
            item_scope = scope_from_data(decoded["scope"])
            item_category = str(decoded["category"])
            if scope is not None and item_scope != scope:
                continue
            if category is not None and item_category != category:
                continue
            values.append(WorkspaceAllocation(
                workspace_id=str(decoded["workspace_id"]),
                scope=item_scope,
                category=item_category,
                path=metadata.parent,
                owner=(str(decoded["owner"]) if decoded.get("owner") is not None else None),
                note=(str(decoded["note"]) if decoded.get("note") is not None else None),
            ))
        return tuple(values)

    def remove_workspace(self, workspace_id: str, *, scope: ScopeIdentity, category: str = "default") -> bool:
        self._validate_name(workspace_id, "workspace_id")
        self._validate_name(category, "category")
        path = self._path(scope, category, workspace_id)
        if not path.exists():
            return False
        shutil.rmtree(path)
        return True

    @staticmethod
    def _validate_name(value: str, label: str) -> None:
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(f"invalid {label}")


__all__ = ["LocalWorkspaceManager"]
