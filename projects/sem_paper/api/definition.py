from __future__ import annotations

from research_platform.portfolio.project.api import (
    ProjectDefinition,
    ProjectIdentity,
    ProjectMethodRequirement,
    SystemCapabilityRequirement,
)


PROJECT_DEFINITION = ProjectDefinition(
    identity=ProjectIdentity("sem-paper-1", "1"),
    capabilities=(
        SystemCapabilityRequirement("participant", "method.runtime"),
        SystemCapabilityRequirement("experimentation", "experiment.runtime"),
        SystemCapabilityRequirement("scientific", "measurement"),
        SystemCapabilityRequirement("observability", "logging"),
        SystemCapabilityRequirement("observability", "capture"),
        SystemCapabilityRequirement("reliability", "forensics"),
        SystemCapabilityRequirement("artifact", "catalog"),
        SystemCapabilityRequirement("data", "state"),
    ),
    methods=(
        ProjectMethodRequirement("self_evolving_memory", "fixed_memory"),
        ProjectMethodRequirement("self_evolving_memory", "self_evolving"),
    ),
)


__all__ = ["PROJECT_DEFINITION"]
