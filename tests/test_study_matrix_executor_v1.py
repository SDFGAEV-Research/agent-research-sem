from research_platform.experimentation.study import (
    BasicStudyMetricAggregator,
    DeterministicStudyAssignment,
    StudyExecutionUnit,
    StudyMatrixExecutor,
    StudyMetricObservation,
    StudyProtocol,
    StudyVariantSpec,
    VariantKind,
)


def _protocol() -> StudyProtocol:
    return StudyProtocol(
        "study-matrix",
        "workload-matrix",
        (
            StudyVariantSpec("control", VariantKind.CONTROL, "fixed", "a" * 64),
            StudyVariantSpec("treatment", VariantKind.TREATMENT, "candidate", "b" * 64),
        ),
        2,
        "c" * 64,
        ("score",),
        "d" * 64,
    )


class _Adapter:
    def execute(self, unit: StudyExecutionUnit):
        return tuple(
            StudyMetricObservation(assignment, (("score", float(unit.repetition + 1)),))
            for assignment in unit.assignments
        )


def test_matrix_executor_groups_repetitions_and_returns_complete_report() -> None:
    protocol = _protocol()
    assignments = DeterministicStudyAssignment().assignments(protocol)
    report = StudyMatrixExecutor(BasicStudyMetricAggregator()).execute(
        protocol,
        assignments,
        _Adapter(),
    )
    assert report.protocol_digest == protocol.protocol_digest
    assert len(report.observations) == 4
    assert {(item.variant_id, item.count) for item in report.aggregates} == {
        ("control", 2),
        ("treatment", 2),
    }
