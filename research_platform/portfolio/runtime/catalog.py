from __future__ import annotations

from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeRegistryPort
from research_platform.portfolio.api import ProgramSpec, ProjectManifest, WorkspaceSpec


class PortfolioConflict(RuntimeError):
    pass


class PortfolioNotFound(KeyError):
    pass


class InMemoryPortfolioCatalog:
    """Portfolio metadata authority; hierarchy itself is owned by Scope System."""

    def __init__(self, scopes: ScopeRegistryPort) -> None:
        self._scopes = scopes
        self._workspaces: dict[str, WorkspaceSpec] = {}
        self._programs: dict[str, ProgramSpec] = {}
        self._projects: dict[str, ProjectManifest] = {}

    def register_workspace(self, spec: WorkspaceSpec) -> None:
        self._put(self._workspaces, spec.workspace_id, spec)
        self._scopes.register(spec.scope, PLATFORM_SCOPE)

    def register_program(self, spec: ProgramSpec) -> None:
        if spec.workspace_id not in self._workspaces:
            raise PortfolioNotFound(f"workspace not registered: {spec.workspace_id}")
        self._put(self._programs, spec.program_id, spec)
        self._scopes.register(spec.scope, self.workspace(spec.workspace_id).scope)

    def register_project(self, manifest: ProjectManifest) -> None:
        spec = manifest.project
        if spec.program_id not in self._programs:
            raise PortfolioNotFound(f"program not registered: {spec.program_id}")
        self._put(self._projects, spec.project_id, manifest)
        self._scopes.register(spec.scope, self.program(spec.program_id).scope)

    @staticmethod
    def _put(store: dict[str, object], key: str, value: object) -> None:
        current = store.get(key)
        if current is not None and current != value:
            raise PortfolioConflict(f"identity already registered with different content: {key}")
        store[key] = value

    def workspace(self, workspace_id: str) -> WorkspaceSpec:
        try:
            return self._workspaces[workspace_id]
        except KeyError as exc:
            raise PortfolioNotFound(workspace_id) from exc

    def program(self, program_id: str) -> ProgramSpec:
        try:
            return self._programs[program_id]
        except KeyError as exc:
            raise PortfolioNotFound(program_id) from exc

    def project(self, project_id: str) -> ProjectManifest:
        try:
            return self._projects[project_id]
        except KeyError as exc:
            raise PortfolioNotFound(project_id) from exc

    def projects(self, *, program_id: str | None = None) -> tuple[ProjectManifest, ...]:
        rows = self._projects.values()
        if program_id is not None:
            rows = (row for row in rows if row.project.program_id == program_id)
        return tuple(sorted(rows, key=lambda row: row.project.project_id))


__all__ = ["InMemoryPortfolioCatalog", "PortfolioConflict", "PortfolioNotFound"]
