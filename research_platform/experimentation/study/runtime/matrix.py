from __future__ import annotations

from collections import defaultdict

from ..api import (
    BoundStudyUnitExecutionPort,
    ExperimentPlan,
    StudyAssignment,
    StudyExecutionUnit,
    StudyMatrixExecutionReport,
    StudyMetricAggregationPort,
    StudyMetricObservation,
    StudyProtocol,
    StudyUnitExecutionPort,
)
from .protocol import DeterministicStudyAssignment


class StudyMatrixExecutor:
    """Run every declared assignment through one injected environment adapter.

    Matrix completeness, repetition grouping and aggregate invocation are
    platform responsibilities. The adapter owns environment and branch
    mechanics only.
    """

    def __init__(
        self,
        aggregation: StudyMetricAggregationPort,
        assignment_expander: DeterministicStudyAssignment | None = None,
    ) -> None:
        self._aggregation = aggregation
        self._assignment_expander = assignment_expander or DeterministicStudyAssignment()

    def execute(
        self,
        protocol: StudyProtocol,
        assignments: tuple[StudyAssignment, ...],
        adapter: StudyUnitExecutionPort,
    ) -> StudyMatrixExecutionReport:
        expected = self._assignment_expander.assignments(protocol)
        self._require_exact_assignments(expected, assignments)
        grouped: dict[int, list[StudyAssignment]] = defaultdict(list)
        for assignment in assignments:
            grouped[assignment.repetition].append(assignment)

        observations: list[StudyMetricObservation] = []
        for repetition in sorted(grouped):
            unit = StudyExecutionUnit(
                protocol.study_id,
                repetition,
                tuple(sorted(grouped[repetition], key=lambda item: item.variant_id)),
            )
            unit_observations = tuple(adapter.execute(unit))
            expected_digests = {item.assignment_digest for item in unit.assignments}
            actual_digests = tuple(item.assignment.assignment_digest for item in unit_observations)
            if len(actual_digests) != len(set(actual_digests)):
                raise ValueError(f"study unit returned duplicate observations: repetition={repetition}")
            if set(actual_digests) != expected_digests:
                raise ValueError(
                    "study unit did not return exactly one observation per assignment: "
                    f"repetition={repetition}"
                )
            observations.extend(sorted(unit_observations, key=lambda item: item.assignment.variant_id))

        frozen_observations = tuple(observations)
        aggregates = self._aggregation.aggregate(protocol, frozen_observations)
        return StudyMatrixExecutionReport(protocol.protocol_digest, frozen_observations, aggregates)

    def execute_plan(
        self,
        plan: ExperimentPlan,
        assignments: tuple[StudyAssignment, ...],
        adapter: BoundStudyUnitExecutionPort,
    ) -> StudyMatrixExecutionReport:
        """Execute a compiled plan through its complete binding set.

        This is intentionally a distinct port from the legacy protocol-only
        path. A plan run must not silently downgrade to an adapter that can
        only interpret ``control`` and ``treatment`` by kind.
        """

        plan.assert_consistent()
        execute_bound = getattr(adapter, "execute_bound", None)
        if not callable(execute_bound):
            raise TypeError(
                "compiled experiment plans require an adapter implementing execute_bound"
            )
        expected = self._assignment_expander.assignments(plan.protocol)
        self._require_exact_assignments(expected, assignments)
        grouped: dict[int, list[StudyAssignment]] = defaultdict(list)
        for assignment in assignments:
            grouped[assignment.repetition].append(assignment)

        observations: list[StudyMetricObservation] = []
        for repetition in sorted(grouped):
            unit = StudyExecutionUnit(
                plan.protocol.study_id,
                repetition,
                tuple(sorted(grouped[repetition], key=lambda item: item.variant_id)),
            )
            unit_bindings = tuple(plan.binding_for(item.variant_id) for item in unit.assignments)
            unit_observations = tuple(
                execute_bound(unit, unit_bindings, plan.plan_digest)
            )
            self._require_exact_observations(unit, unit_observations, repetition)
            observations.extend(sorted(unit_observations, key=lambda item: item.assignment.variant_id))

        frozen_observations = tuple(observations)
        aggregates = self._aggregation.aggregate(plan.protocol, frozen_observations)
        return StudyMatrixExecutionReport(
            plan.protocol.protocol_digest,
            frozen_observations,
            aggregates,
            binding_digest=plan.binding_digest,
            plan_digest=plan.plan_digest,
        )

    @staticmethod
    def _require_exact_observations(
        unit: StudyExecutionUnit,
        observations: tuple[StudyMetricObservation, ...],
        repetition: int,
    ) -> None:
        expected_digests = {item.assignment_digest for item in unit.assignments}
        actual_digests = tuple(item.assignment.assignment_digest for item in observations)
        if len(actual_digests) != len(set(actual_digests)):
            raise ValueError(f"study unit returned duplicate observations: repetition={repetition}")
        if set(actual_digests) != expected_digests:
            raise ValueError(
                "study unit did not return exactly one observation per assignment: "
                f"repetition={repetition}"
            )

    @staticmethod
    def _require_exact_assignments(
        expected: tuple[StudyAssignment, ...],
        actual: tuple[StudyAssignment, ...],
    ) -> None:
        expected_digests = tuple(item.assignment_digest for item in expected)
        actual_digests = tuple(item.assignment_digest for item in actual)
        if len(actual_digests) != len(set(actual_digests)):
            raise ValueError("study assignment matrix contains duplicate assignments")
        if set(expected_digests) != set(actual_digests):
            raise ValueError("study assignment matrix is not exactly the declared protocol")


__all__ = ["StudyMatrixExecutor"]
