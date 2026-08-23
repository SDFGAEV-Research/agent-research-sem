from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from research_platform.experimentation.run.api.spec import ExperimentRunSpec
from research_platform.experimentation.study.api import (
    StudyMatrixExecutionReport,
    StudyProtocol,
    StudyUnitExecutionPort,
)


@dataclass(frozen=True, slots=True)
class ExperimentRunResult:
    """Run-owned envelope around the direct Study child result."""

    run_spec_digest: str
    protocol_digest: str
    study_report: StudyMatrixExecutionReport

    def __post_init__(self) -> None:
        if len(self.run_spec_digest) != 64 or len(self.protocol_digest) != 64:
            raise ValueError("experiment run result identities must be SHA-256 digests")
        if self.study_report.protocol_digest != self.protocol_digest:
            raise ValueError("experiment run result protocol digest is inconsistent")


class ExperimentRunExecutionPort(Protocol):
    """Run-layer parent port for one frozen scientific study.

    The run system owns the lifecycle of the generic study execution.  The
    injected unit adapter owns only environment realization; it may be MC,
    closed-world, simulator-backed, or another future environment.
    """

    def execute(
        self,
        *,
        run_spec: ExperimentRunSpec,
        protocol: StudyProtocol,
        unit_adapter: StudyUnitExecutionPort,
    ) -> ExperimentRunResult: ...


__all__ = ["ExperimentRunExecutionPort", "ExperimentRunResult"]
