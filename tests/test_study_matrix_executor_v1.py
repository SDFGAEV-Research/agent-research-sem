from threading import Lock
import time

from research_platform.platform.concurrency.api import ConcurrencyBudget, TaskFailurePolicy
from research_platform.platform.concurrency.composition import build_concurrency_runtime
from research_platform.experimentation.study import (
    BasicStudyMetricAggregator,
    DeterministicStudyAssignment,
    ScientificConcurrencyPolicy,
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



def test_parallel_repetition_policy_uses_structured_concurrency_and_deterministic_merge() -> None:
    protocol = StudyProtocol(
        "study-parallel",
        "workload-parallel",
        (
            StudyVariantSpec("control", VariantKind.CONTROL, "fixed", "a" * 64),
            StudyVariantSpec("treatment", VariantKind.TREATMENT, "candidate", "b" * 64),
        ),
        4,
        "c" * 64,
        ("score",),
        "d" * 64,
        concurrency_policy=ScientificConcurrencyPolicy(max_parallel_repetitions=2),
    )
    assignments = DeterministicStudyAssignment().assignments(protocol)
    runtime = build_concurrency_runtime(
        budget=ConcurrencyBudget(
            max_blocking_io_workers=2,
            max_cpu_workers=1,
            default_queue_capacity=4,
        )
    )
    group = runtime.open_task_group("study-parallel-execution", failure_policy=TaskFailurePolicy.COLLECT_ALL)
    active = 0
    max_active = 0
    lock = Lock()

    class ParallelAdapter:
        def execute(self, unit: StudyExecutionUnit):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.04)
                return tuple(
                    StudyMetricObservation(
                        assignment,
                        (("score", float(unit.repetition + 1)),),
                    )
                    for assignment in unit.assignments
                )
            finally:
                with lock:
                    active -= 1

    try:
        report = StudyMatrixExecutor(
            BasicStudyMetricAggregator(),
            task_group=group,
        ).execute(protocol, assignments, ParallelAdapter())
        assert max_active == 2
        assert [item.assignment.repetition for item in report.observations] == [0, 0, 1, 1, 2, 2, 3, 3]
        assert [item.assignment.variant_id for item in report.observations[:2]] == ["control", "treatment"]
    finally:
        group.close()
        runtime.close()


def test_scientific_concurrency_policy_is_part_of_protocol_identity() -> None:
    serial = _protocol()
    parallel = StudyProtocol(
        serial.study_id,
        serial.workload_id,
        serial.variants,
        serial.repetitions,
        serial.seed_schedule_digest,
        serial.metric_names,
        serial.task_manifest_digest,
        concurrency_policy=ScientificConcurrencyPolicy(max_parallel_repetitions=2),
    )
    assert serial.protocol_digest != parallel.protocol_digest
