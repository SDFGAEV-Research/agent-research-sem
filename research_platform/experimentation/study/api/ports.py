from __future__ import annotations

from typing import Protocol

from .contracts import (
    StudyAssignment,
    StudyExecutionUnit,
    StudyMetricAggregate,
    StudyMetricObservation,
    StudyMatrixExecutionReport,
    StudyProtocol,
)


class StudyAssignmentPort(Protocol):
    def assignments(self, protocol: StudyProtocol) -> tuple[StudyAssignment, ...]: ...


class StudyMetricAggregationPort(Protocol):
    def aggregate(
        self,
        protocol: StudyProtocol,
        observations: tuple[StudyMetricObservation, ...],
    ) -> tuple[StudyMetricAggregate, ...]: ...


class StudyUnitExecutionPort(Protocol):
    """Environment-neutral adapter for one complete repetition group."""

    def execute(self, unit: StudyExecutionUnit) -> tuple[StudyMetricObservation, ...]: ...


class StudyMatrixExecutionPort(Protocol):
    """Platform execution seam for one complete frozen study matrix."""

    def execute(
        self,
        protocol: StudyProtocol,
        assignments: tuple[StudyAssignment, ...],
        adapter: StudyUnitExecutionPort,
    ) -> StudyMatrixExecutionReport: ...


class StudyArtifactPublicationPort(Protocol):
    """Durable publication seam for frozen protocol and derived statistics."""

    def publish_protocol(
        self,
        protocol: StudyProtocol,
        assignments: tuple[StudyAssignment, ...],
    ) -> str: ...

    def publish_observations(
        self,
        observations: tuple[StudyMetricObservation, ...],
    ) -> str: ...

    def publish_aggregates(
        self,
        aggregates: tuple[StudyMetricAggregate, ...],
    ) -> str: ...


__all__ = [
    "StudyArtifactPublicationPort",
    "StudyAssignmentPort",
    "StudyMetricAggregationPort",
    "StudyMatrixExecutionPort",
    "StudyUnitExecutionPort",
]
