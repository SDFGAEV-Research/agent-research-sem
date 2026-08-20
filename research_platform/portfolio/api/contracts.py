from __future__ import annotations

from dataclasses import dataclass

from research_platform.scope.api import ScopeIdentity, ScopeKind


@dataclass(frozen=True, slots=True)
class WorkspaceSpec:
    workspace_id: str
    name: str
    description: str = ""

    @property
    def scope(self) -> ScopeIdentity:
        return ScopeIdentity(ScopeKind.WORKSPACE, self.workspace_id)


@dataclass(frozen=True, slots=True)
class ProgramSpec:
    program_id: str
    workspace_id: str
    name: str
    description: str = ""

    @property
    def scope(self) -> ScopeIdentity:
        return ScopeIdentity(ScopeKind.PROGRAM, self.program_id)


@dataclass(frozen=True, slots=True)
class ProjectSpec:
    project_id: str
    program_id: str
    name: str
    description: str = ""
    tags: tuple[str, ...] = ()

    @property
    def scope(self) -> ScopeIdentity:
        return ScopeIdentity(ScopeKind.PROJECT, self.project_id)


@dataclass(frozen=True, slots=True)
class ProjectManifest:
    project: ProjectSpec
    method_implementation_id: str | None = None
    agent_implementation_id: str | None = None
    environment_implementation_id: str | None = None
    default_environment_spec_id: str | None = None
    model_assignments: tuple[tuple[str, str], ...] = ()
    study_ids: tuple[str, ...] = ()


__all__ = ["ProgramSpec", "ProjectManifest", "ProjectSpec", "WorkspaceSpec"]
