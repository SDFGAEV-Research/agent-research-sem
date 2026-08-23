from __future__ import annotations

from research_platform.experimentation.run.api import ExperimentRunSpec
from research_platform.experimentation.run.runtime import ExperimentRunApplication
from research_platform.experimentation.study.api import (
    StudyMetricObservation,
    StudyProtocol,
    StudyVariantSpec,
    VariantKind,
)
from research_platform.experimentation.study.runtime import (
    BasicStudyMetricAggregator,
    DeterministicStudyAssignment,
    StudyMatrixExecutor,
)
from research_platform.platform.kernel import canonical_digest


class _Publication:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def publish_protocol(self, protocol, assignments):
        del protocol, assignments
        self.calls.append("protocol")
        return "protocol"

    def publish_observations(self, observations):
        del observations
        self.calls.append("observations")
        return "observations"

    def publish_aggregates(self, aggregates):
        del aggregates
        self.calls.append("aggregates")
        return "aggregates"


class _UnitAdapter:
    def execute(self, unit):
        return tuple(
            StudyMetricObservation(assignment, (("score", float(unit.repetition + 1)),))
            for assignment in unit.assignments
        )


def test_run_parent_owns_study_expansion_execution_and_publication() -> None:
    protocol = StudyProtocol(
        study_id="study-1",
        workload_id="workload-1",
        variants=(
            StudyVariantSpec("control", VariantKind.CONTROL, "fixed", "a" * 64),
            StudyVariantSpec("treatment", VariantKind.TREATMENT, "candidate", "b" * 64),
        ),
        repetitions=2,
        seed_schedule_digest="c" * 64,
        metric_names=("score",),
        task_manifest_digest="d" * 64,
    )
    run_spec = ExperimentRunSpec(
        run_id="run-1",
        project_id="project-1",
        experiment_id="experiment-1",
        study_id=protocol.study_id,
        execution_profile="test",
        task_manifest_digest=protocol.task_manifest_digest,
        seed_schedule_digest=protocol.seed_schedule_digest,
        repetitions=protocol.repetitions,
        artifact_root="runs/run-1",
        environment_identity_digest=canonical_digest("environment"),
    )
    publication = _Publication()
    application = ExperimentRunApplication(
        assignments=DeterministicStudyAssignment(),
        matrix=StudyMatrixExecutor(BasicStudyMetricAggregator()),
        publication=publication,
    )

    result = application.execute(
        run_spec=run_spec,
        protocol=protocol,
        unit_adapter=_UnitAdapter(),
    )

    assert result.run_spec_digest == run_spec.identity_digest()
    assert result.protocol_digest == protocol.protocol_digest
    assert len(result.study_report.observations) == 4
    assert publication.calls == ["protocol", "observations", "aggregates"]
