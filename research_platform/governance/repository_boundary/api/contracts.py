from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RepositoryBoundaryViolation:
    code: str
    path: str
    detail: str


@dataclass(frozen=True, slots=True)
class RepositoryBoundaryReport:
    schema: str
    violations: tuple[RepositoryBoundaryViolation, ...]

    @property
    def passed(self) -> bool:
        return not self.violations


__all__ = ["RepositoryBoundaryReport", "RepositoryBoundaryViolation"]
