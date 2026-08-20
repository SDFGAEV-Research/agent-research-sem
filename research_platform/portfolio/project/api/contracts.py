from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProjectIdentity:
    """Stable identity of one independently composed project/application."""

    project_id: str
    version: str

    def __post_init__(self) -> None:
        if not self.project_id.strip() or not self.version.strip():
            raise ValueError("project identity fields must be non-empty")


@dataclass(frozen=True, slots=True)
class SystemCapabilityRequirement:
    """A project-level request for a public system capability.

    The requirement names a capability, never a concrete runtime/provider.  The
    platform host resolves the requirement to an implementation during composition.
    """

    system: str
    capability: str
    required: bool = True

    def __post_init__(self) -> None:
        if not self.system.strip() or not self.capability.strip():
            raise ValueError("system capability requirement fields must be non-empty")

    @property
    def key(self) -> str:
        return f"{self.system}:{self.capability}"


@dataclass(frozen=True, slots=True)
class ProjectMethodRequirement:
    """Scientific method/treatment required by a project."""

    method_id: str
    treatment_id: str

    def __post_init__(self) -> None:
        if not self.method_id.strip() or not self.treatment_id.strip():
            raise ValueError("project method requirement fields must be non-empty")


@dataclass(frozen=True, slots=True)
class ProjectDefinition:
    """Declarative project contract consumed by a platform host/composition engine."""

    identity: ProjectIdentity
    capabilities: tuple[SystemCapabilityRequirement, ...]
    methods: tuple[ProjectMethodRequirement, ...] = ()

    def __post_init__(self) -> None:
        capability_keys = tuple(item.key for item in self.capabilities)
        if len(set(capability_keys)) != len(capability_keys):
            raise ValueError("project capability requirements must be unique")
        method_keys = tuple((item.method_id, item.treatment_id) for item in self.methods)
        if len(set(method_keys)) != len(method_keys):
            raise ValueError("project method requirements must be unique")


__all__ = [
    "ProjectDefinition",
    "ProjectIdentity",
    "ProjectMethodRequirement",
    "SystemCapabilityRequirement",
]
