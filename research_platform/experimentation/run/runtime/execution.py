from __future__ import annotations

from research_platform.experimentation.run.api import ExperimentRunExecutionPort, ExperimentRunResult
from research_platform.experimentation.run.api.spec import ExperimentRunSpec
from research_platform.experimentation.study.api import (
    StudyArtifactPublicationPort,
    StudyAssignmentPort,
    StudyMatrixExecutionPort,
    StudyMatrixExecutionReport,
    StudyProtocol,
    StudyUnitExecutionPort,
)


class ExperimentRunApplication(ExperimentRunExecutionPort):
    """The generic run parent over the direct Study child.

    This is intentionally the only run-level owner of assignment expansion,
    study execution and scientific artifact publication.  Environment roots
    receive this narrow port; they do not each compose a second matrix loop.
    """

    def __init__(
        self,
        *,
        assignments: StudyAssignmentPort,
        matrix: StudyMatrixExecutionPort,
        publication: StudyArtifactPublicationPort,
    ) -> None:
        self._assignments = assignments
        self._matrix = matrix
        self._publication = publication

    def execute(
        self,
        *,
        run_spec: ExperimentRunSpec,
        protocol: StudyProtocol,
        unit_adapter: StudyUnitExecutionPort,
    ) -> ExperimentRunResult:
        self._validate_run_identity(run_spec, protocol)
        assignments = self._assignments.assignments(protocol)
        if not assignments:
            raise ValueError("experiment run requires at least one frozen study assignment")
        self._publication.publish_protocol(protocol, assignments)
        report = self._matrix.execute(protocol, assignments, unit_adapter)
        self._publication.publish_observations(report.observations)
        self._publication.publish_aggregates(report.aggregates)
        return ExperimentRunResult(
            run_spec_digest=run_spec.identity_digest(),
            protocol_digest=protocol.protocol_digest,
            study_report=report,
        )

    @staticmethod
    def _validate_run_identity(
        run_spec: ExperimentRunSpec,
        protocol: StudyProtocol,
    ) -> None:
        if run_spec.study_id != protocol.study_id:
            raise ValueError("experiment run specification belongs to another study")
        if run_spec.task_manifest_digest != protocol.task_manifest_digest:
            raise ValueError("experiment run task digest does not match study protocol")
        if run_spec.seed_schedule_digest != protocol.seed_schedule_digest:
            raise ValueError("experiment run seed digest does not match study protocol")
        if run_spec.repetitions != protocol.repetitions:
            raise ValueError("experiment run repetition count does not match study protocol")


__all__ = ["ExperimentRunApplication"]
