from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import canonical_digest
from research_platform.experimentation.experiment.api import ExperimentParticipantSpec, ExperimentSpec


@dataclass(frozen=True, slots=True)
class ExperimentParticipantTopology:
    participants: tuple[ExperimentParticipantSpec, ...]

    @classmethod
    def from_spec(cls, spec: ExperimentSpec) -> "ExperimentParticipantTopology":
        topology = cls(spec.participants)
        topology.validate()
        return topology

    def validate(self) -> None:
        roles = [row.role for row in self.participants]
        if len(roles) != len(set(roles)):
            raise ValueError("Experiment participant roles must be unique")
        known = set(roles)
        for row in self.participants:
            missing = set(row.depends_on_roles) - known
            if missing:
                raise ValueError(f"participant {row.role} has missing dependencies: {sorted(missing)}")
        self.ordered()

    def ordered(self) -> tuple[ExperimentParticipantSpec, ...]:
        by_role = {row.role: row for row in self.participants}
        pending = {role: set(row.depends_on_roles) for role, row in by_role.items()}
        ordered: list[ExperimentParticipantSpec] = []
        while pending:
            ready = [role for role, deps in pending.items() if not deps]
            if not ready:
                raise ValueError(f"participant dependency cycle: {sorted(pending)}")
            for row in self.participants:
                if row.role not in ready:
                    continue
                ordered.append(row)
                pending.pop(row.role)
                for deps in pending.values():
                    deps.discard(row.role)
        return tuple(ordered)

    def digest(self) -> str:
        return canonical_digest(self)


__all__ = ["ExperimentParticipantTopology"]
