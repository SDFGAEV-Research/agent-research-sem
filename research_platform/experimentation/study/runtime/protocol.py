from __future__ import annotations

import math

from research_platform.platform.kernel import canonical_digest

from ..api import (
    StudyAssignment,
    StudyAssignmentPort,
    StudyMetricAggregate,
    StudyMetricAggregationPort,
    StudyMetricObservation,
    StudyProtocol,
)


class DeterministicStudyAssignment(StudyAssignmentPort):
    """Expand every declared variant and repetition without hidden sampling."""

    def assignments(self, protocol: StudyProtocol) -> tuple[StudyAssignment, ...]:
        return tuple(
            StudyAssignment(
                protocol.study_id,
                variant.variant_id,
                repetition,
                canonical_digest(
                    {
                        "study_id": protocol.study_id,
                        "workload_id": protocol.workload_id,
                        "variant_id": variant.variant_id,
                        "repetition": repetition,
                        "seed_schedule_digest": protocol.seed_schedule_digest,
                    }
                ),
            )
            for repetition in range(protocol.repetitions)
            for variant in protocol.variants
        )


class BasicStudyMetricAggregator(StudyMetricAggregationPort):
    """Pure mean/variance aggregation; no significance claim is implied."""

    def aggregate(
        self,
        protocol: StudyProtocol,
        observations: tuple[StudyMetricObservation, ...],
    ) -> tuple[StudyMetricAggregate, ...]:
        expected = DeterministicStudyAssignment().assignments(protocol)
        expected_by_digest = {item.assignment_digest: item for item in expected}
        observed_by_digest: dict[str, StudyMetricObservation] = {}
        expected_names = set(protocol.metric_names)
        for observation in observations:
            digest = observation.assignment.assignment_digest
            if digest in observed_by_digest:
                raise ValueError(f"study contains duplicate assignment observation: {digest}")
            if digest not in expected_by_digest:
                raise ValueError("study observation references an undeclared assignment")
            actual_names = {name for name, _ in observation.metrics}
            if actual_names != expected_names:
                missing = sorted(expected_names - actual_names)
                extra = sorted(actual_names - expected_names)
                raise ValueError(
                    "study observation metric schema is incomplete: "
                    f"missing={missing!r} extra={extra!r}"
                )
            observed_by_digest[digest] = observation
        missing_assignments = set(expected_by_digest) - set(observed_by_digest)
        if missing_assignments:
            raise ValueError(
                "study matrix is incomplete; missing assignment observations: "
                + ", ".join(sorted(missing_assignments))
            )
        allowed = set(protocol.metric_names)
        grouped: dict[tuple[str, str], list[float]] = {}
        for observation in observations:
            if observation.assignment.study_id != protocol.study_id:
                raise ValueError("study observation belongs to another study")
            for name, value in observation.metrics:
                if name not in allowed:
                    raise ValueError(f"study observation contains undeclared metric: {name}")
                grouped.setdefault((observation.assignment.variant_id, name), []).append(float(value))
        aggregates: list[StudyMetricAggregate] = []
        for (variant_id, name), values in sorted(grouped.items()):
            count = len(values)
            mean = sum(values) / count
            variance = (
                sum((value - mean) ** 2 for value in values) / (count - 1)
                if count > 1
                else 0.0
            )
            aggregates.append(
                StudyMetricAggregate(
                    protocol.study_id,
                    variant_id,
                    name,
                    count,
                    mean,
                    variance,
                    math.sqrt(variance / count),
                )
            )
        return tuple(aggregates)


__all__ = ["BasicStudyMetricAggregator", "DeterministicStudyAssignment"]
