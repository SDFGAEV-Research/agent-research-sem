from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from ..architecture import MemoryArchitectureSpec

from research_platform.experimentation.evaluation.api import ComparabilityProof
from research_platform.platform.kernel import ExecutionContext, JsonValue


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
class NodeObservationProfile:
    """Typed, neutral runtime facts shared by every evolution proposal policy."""

    node_id: str
    selected_count: int = 0
    result_count: int = 0
    query_count: int = 0
    empty_result_count: int = 0
    update_count: int = 0
    records_added: int = 0
    records_removed: int = 0

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("node observation profile requires a node id")
        values = (
            self.selected_count,
            self.result_count,
            self.query_count,
            self.empty_result_count,
            self.update_count,
            self.records_added,
            self.records_removed,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise ValueError("node observation counts must be non-negative integers")


@dataclass(frozen=True, slots=True)
class NodePairObservation:
    """Neutral co-selection fact; it carries no edit recommendation."""

    pair_id: str
    left_node_id: str
    right_node_id: str
    co_select_count: int

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.pair_id, self.left_node_id, self.right_node_id)):
            raise ValueError("node pair observation identity is required")
        if self.left_node_id == self.right_node_id or self.co_select_count < 0:
            raise ValueError("node pair observation is invalid")


@dataclass(frozen=True, slots=True)
class UnresolvedIntentCluster:
    """Ontology-free unresolved-intent support exposed to proposal policies."""

    cluster_id: str
    support: int
    examples: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.cluster_id.strip() or self.support <= 0:
            raise ValueError("unresolved intent cluster identity/support is invalid")
        if any(not example.strip() for example in self.examples):
            raise ValueError("unresolved intent cluster examples must be non-empty")


@dataclass(frozen=True, slots=True)
class ArchitectureObservationReport:
    generation: str
    neutral_summary: str
    evidence_refs: tuple[str, ...]
    architecture: MemoryArchitectureSpec | None = None
    node_profiles: tuple[NodeObservationProfile, ...] = ()
    pairs: tuple[NodePairObservation, ...] = ()
    incident_counts: tuple[tuple[str, int], ...] = ()
    unresolved_intent_clusters: tuple[UnresolvedIntentCluster, ...] = ()

    def __post_init__(self) -> None:
        if not self.generation.strip() or not self.neutral_summary.strip():
            raise ValueError("architecture observation report identity is required")
        if any(not ref.strip() for ref in self.evidence_refs):
            raise ValueError("architecture observation evidence refs must be non-empty")
        profile_ids = tuple(profile.node_id for profile in self.node_profiles)
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("architecture observation contains duplicate node profiles")
        if self.architecture is not None:
            unknown = set(profile_ids) - set(self.architecture.node_map())
            if unknown:
                raise ValueError(
                    "architecture observation contains profiles for unknown nodes: "
                    f"{sorted(unknown)}"
                )
        pair_ids = tuple(pair.pair_id for pair in self.pairs)
        if len(pair_ids) != len(set(pair_ids)):
            raise ValueError("architecture observation contains duplicate node pairs")
        if any(not name.strip() or count < 0 for name, count in self.incident_counts):
            raise ValueError("architecture observation incident counts are invalid")
        if len({name for name, _ in self.incident_counts}) != len(self.incident_counts):
            raise ValueError("architecture observation contains duplicate incident kinds")


@dataclass(frozen=True, slots=True)
class StructuralIntent:
    edit: EditKind
    rationale: str
    payload: JsonValue | None = None


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
