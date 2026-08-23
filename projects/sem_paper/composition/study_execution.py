from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from research_platform.environment.minecraft.api import MinecraftWorldCutPort
from research_platform.experimentation.evaluation.api import BranchReceipt
from research_platform.experimentation.study.api import (
    StudyAssignment,
    StudyExecutionUnit,
    StudyMetricObservation,
    StudyProtocol,
    StudyUnitExecutionPort,
    VariantKind,
)
from research_platform.platform.kernel import ExecutionContext

from projects.sem_paper.method.self_evolving_memory.evolution import (
    BranchRole,
    CandidateArchitecture,
    PairedBranchEvaluator,
)

from .minecraft_branch import MinecraftPairedBranchRunner
from .minecraft_workload_executor import MinecraftWorkloadBranchExecutor


class SemPaperStudyUnitError(RuntimeError):
    """A project study unit cannot be represented by the bound adapter."""


def _paired_assignments(
    protocol: StudyProtocol,
    unit: StudyExecutionUnit,
) -> tuple[StudyAssignment, StudyAssignment]:
    if unit.study_id != protocol.study_id:
        raise SemPaperStudyUnitError("study unit belongs to another study")
    if len(unit.assignments) != 2:
        raise SemPaperStudyUnitError(
            "the current SEM paired adapter requires exactly one control and one treatment assignment"
        )
    by_kind: dict[VariantKind, StudyAssignment] = {}
    variant_by_id = {item.variant_id: item for item in protocol.variants}
    for assignment in unit.assignments:
        variant = variant_by_id.get(assignment.variant_id)
        if variant is None:
            raise SemPaperStudyUnitError("study unit references an undeclared variant")
        if variant.kind in by_kind:
            raise SemPaperStudyUnitError(
                f"the current SEM paired adapter cannot represent two {variant.kind.value} variants"
            )
        by_kind[variant.kind] = assignment
    if set(by_kind) != {VariantKind.CONTROL, VariantKind.TREATMENT}:
        raise SemPaperStudyUnitError(
            "the current SEM paired adapter requires one control and one treatment variant"
        )
    return by_kind[VariantKind.CONTROL], by_kind[VariantKind.TREATMENT]


def _receipt_observation(
    assignment: StudyAssignment,
    receipt: BranchReceipt,
    protocol: StudyProtocol,
) -> StudyMetricObservation:
    metrics = dict(receipt.metrics)
    values: list[tuple[str, float]] = []
    for name in protocol.metric_names:
        if name not in metrics:
            raise SemPaperStudyUnitError(
                f"branch receipt is missing declared study metric: {name}"
            )
        values.append((name, float(metrics[name])))
    return StudyMetricObservation(assignment, tuple(values))


@dataclass(frozen=True, slots=True)
class SemPaperMinecraftStudyUnitAdapter(StudyUnitExecutionPort):
    """Run one complete SEM paired unit through a fresh MC source cut.

    The adapter owns only MC realization.  Assignment completeness, repetition
    grouping and aggregate computation remain in ``StudyMatrixExecutor``.
    """

    protocol: StudyProtocol
    candidate: CandidateArchitecture
    world_cuts: MinecraftWorldCutPort
    workload_executor: MinecraftWorkloadBranchExecutor
    session_id: str
    context: ExecutionContext | None
    branch_id_factory: Callable[[BranchRole, int], str]
    destination_factory: Callable[[str], str]

    def execute(self, unit: StudyExecutionUnit) -> tuple[StudyMetricObservation, ...]:
        control_assignment, treatment_assignment = _paired_assignments(self.protocol, unit)
        runner = MinecraftPairedBranchRunner(
            world_cuts=self.world_cuts,
            executor=self.workload_executor,
            session_id=f"{self.session_id}:rep-{unit.repetition}",
            context=self.context,
            branch_id_factory=lambda role: self.branch_id_factory(role, unit.repetition),
            destination_factory=self.destination_factory,
        )
        runner.prepare_source_cut()
        evaluation = PairedBranchEvaluator(runner).evaluate_with_receipts(self.candidate)
        if not evaluation.proof.comparability.valid:
            raise SemPaperStudyUnitError(
                f"Minecraft study unit comparability proof failed: repetition={unit.repetition}"
            )
        return (
            _receipt_observation(control_assignment, evaluation.control, self.protocol),
            _receipt_observation(treatment_assignment, evaluation.candidate, self.protocol),
        )


__all__ = [
    "SemPaperMinecraftStudyUnitAdapter",
    "SemPaperStudyUnitError",
]
