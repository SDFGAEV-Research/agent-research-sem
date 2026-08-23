from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from research_platform.experimentation.evaluation.api import ComparabilityProof
from research_platform.platform.kernel import ExecutionContext


class EditKind(StrEnum):
    NO_EDIT = "NO_EDIT"
    CREATE = "CREATE"
    RETIRE = "RETIRE"
    SPLIT = "SPLIT"
    MERGE = "MERGE"


class PrimitiveEditKind(StrEnum):
    CREATE = "CREATE"
    RETIRE = "RETIRE"


class EvolutionStage(StrEnum):
    ELIGIBILITY = "eligibility"
    DIAGNOSIS = "diagnosis"
    SYNTHESIS = "synthesis"
    COMPILATION = "compilation"
    EVALUATION = "evaluation"
    ACCEPTANCE = "acceptance"
    ADOPTION = "adoption"


class EvolutionStageFailure(RuntimeError):
    """Stable stage attribution while preserving the original exception as the cause."""

    def __init__(self, stage: EvolutionStage, cause: BaseException) -> None:
        super().__init__(f"SEM evolution stage failed: {stage.value}")
        self.stage = stage
        self.cause = cause
        self.cause_type = type(cause).__name__

    @property
    def failure_correlation_refs(self) -> tuple[str, ...]:
        return (f"evolution-stage:{self.stage.value}",)


@dataclass(frozen=True, slots=True)
class EvolutionEligibility:
    eligible: bool
    reason_code: str


@dataclass(frozen=True, slots=True)
class ArchitectureObservationReport:
    generation: str
    neutral_summary: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuralIntent:
    edit: EditKind
    rationale: str
    payload: object | None = None


@dataclass(frozen=True, slots=True)
class PrimitiveEdit:
    kind: PrimitiveEditKind
    target: str
    spec: object | None = None


@dataclass(frozen=True, slots=True)
class CandidateArchitecture:
    base_generation: str
    candidate_id: str
    target_spec: object
    target_spec_digest: str
    primitive_edits: tuple[PrimitiveEdit, ...]
    materialization_contracts: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class EvaluationProof:
    comparability: ComparabilityProof
    metrics: dict[str, float]


@dataclass(frozen=True, slots=True)
class EvolutionOutcome:
    status: str
    base_generation: str | None
    final_generation: str | None
    edit: EditKind | None
    reason_code: str | None = None


class EligibilityPort(Protocol):
    def check(self) -> EvolutionEligibility: ...


class DiagnosisPort(Protocol):
    def diagnose(self) -> ArchitectureObservationReport: ...


class SynthesisPort(Protocol):
    def propose(self, aor: ArchitectureObservationReport) -> StructuralIntent: ...


class CompilerPort(Protocol):
    def compile(self, intent: StructuralIntent, base_generation: str) -> CandidateArchitecture: ...


class EvaluatorPort(Protocol):
    def evaluate(self, candidate: CandidateArchitecture) -> EvaluationProof: ...


class AcceptancePort(Protocol):
    def accept(self, intent: StructuralIntent, proof: EvaluationProof) -> bool: ...


class AdoptionPort(Protocol):
    def adopt(self, candidate: CandidateArchitecture, proof: EvaluationProof) -> str: ...


class ContextualAdoptionPort(Protocol):
    """Pipeline adoption stage bound to the exact task execution context."""

    def adopt(
        self,
        candidate: CandidateArchitecture,
        proof: EvaluationProof,
        context: ExecutionContext | None,
    ) -> str: ...
