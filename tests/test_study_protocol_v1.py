from __future__ import annotations

from research_platform.experimentation.study import (
    BasicStudyMetricAggregator,
    DeterministicStudyAssignment,
    StudyMetricObservation,
    StudyProtocol,
    StudyVariantSpec,
    VariantKind,
)
import pytest


def _protocol() -> StudyProtocol:
    return StudyProtocol(
        "study-1",
        "workload-1",
        (
            StudyVariantSpec("control", VariantKind.CONTROL, "memory.fixed", "a" * 64),
            StudyVariantSpec("treatment", VariantKind.TREATMENT, "memory.evolving", "b" * 64),
        ),
        2,
        "c" * 64,
        ("success_rate", "utility"),
        "d" * 64,
    )


def test_study_protocol_expands_full_variant_repetition_matrix_and_aggregates():
    protocol = _protocol()
    assignments = DeterministicStudyAssignment().assignments(protocol)
    assert len(assignments) == 4
    observations = tuple(
        StudyMetricObservation(assignment, (("success_rate", 1.0), ("utility", 2.0)))
        for assignment in assignments
    )
    aggregates = BasicStudyMetricAggregator().aggregate(protocol, observations)
    assert {(item.variant_id, item.metric_name, item.count) for item in aggregates} == {
        ("control", "success_rate", 2),
        ("control", "utility", 2),
        ("treatment", "success_rate", 2),
        ("treatment", "utility", 2),
    }


def test_study_aggregation_rejects_incomplete_matrix() -> None:
    protocol = _protocol()
    assignments = DeterministicStudyAssignment().assignments(protocol)
    observations = tuple(
        StudyMetricObservation(assignments[0], (("success_rate", 1.0), ("utility", 2.0)))
        for _ in (0,)
    )
    with pytest.raises(ValueError, match="matrix is incomplete"):
        BasicStudyMetricAggregator().aggregate(protocol, observations)


def test_study_aggregation_rejects_incomplete_metric_schema() -> None:
    protocol = _protocol()
    assignments = DeterministicStudyAssignment().assignments(protocol)
    observations = tuple(
        StudyMetricObservation(assignment, (("success_rate", 1.0),))
        for assignment in assignments
    )
    with pytest.raises(ValueError, match="metric schema is incomplete"):
        BasicStudyMetricAggregator().aggregate(protocol, observations)
