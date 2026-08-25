"""SEM production evolution composition.

This module is the project-owned composition root for the seven evolution
stages.  Stage implementations remain replaceable ports: the default graph
is evidence-bound and fail-closed until an outer runtime supplies a structural
proposal, paired evaluator, and adoption authority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Protocol

from research_platform.experimentation.evaluation.api import ComparabilityProof
from research_platform.platform.kernel import canonical_digest

from projects.sem_paper.method.self_evolving_memory.architecture import (
    ArchitectureCompiler,
    MemoryArchitectureSpec,
    SemPaperArchitecturePreset,
    build_sem_paper_architecture,
)
from projects.sem_paper.method.self_evolving_memory.architecture.edits import (
    CreateNodeEdit,
    MergeNodesEdit,
    RetireNodeEdit,
    SplitNodeEdit,
)
from projects.sem_paper.method.self_evolving_memory.evolution import (
    AcceptancePort,
    AdoptionPort,
    ArchitectureObservationReport,
    CompilerPort,
    DiagnosisPort,
    EditKind,
    EligibilityPort,
    EvaluationProof,
    EvaluatorPort,
    EvolutionEligibility,
    NodeObservationProfile,
    NodePairObservation,
    PrimitiveEdit,
    StructuralCompiler,
    StructuralIntent,
    SynthesisPort,
    UnresolvedIntentCluster,
)
from projects.sem_paper.method.self_evolving_memory.evolution.diagnostics import AutomaticSliceDiscovery
from projects.sem_paper.method.self_evolving_memory.evolution.compiler import OperationalVerifier
from projects.sem_paper.method.self_evolving_memory.evolution_composition import (
    EvolutionStageFactories,
    PipelineSessionEvolutionFactory,
)
from projects.sem_paper.method.self_evolving_memory.materialization import MaterializationContract
from projects.sem_paper.method.self_evolving_memory.session_evolution_api import (
    EvolutionReconciliationPort,
    EvolutionSessionSource,
    SessionAdoptionAuthority,
    SessionEvolutionFactory,
)
from projects.sem_paper.method.self_evolving_memory.session_evolution_runtime import (
    ConservativeEvolutionReconciler,
)


class StructuralProposalPort(Protocol):
    """Optional external authority for a typed, evidence-backed proposal."""

    def propose(self, report: ArchitectureObservationReport) -> StructuralIntent | None: ...


class EvolutionEvaluationPort(EvaluatorPort, Protocol):
    """Evaluator supplied by the environment-specific paired branch runtime."""


class EvolutionAdoptionPort(AdoptionPort, Protocol):
    """Adoption implementation supplied by the session composition root."""


class _EvidenceEligibility(EligibilityPort):
    def __init__(self, source: EvolutionSessionSource) -> None:
        self._source = source

    def check(self) -> EvolutionEligibility:
        snapshot = self._source.snapshot()
        telemetry = snapshot.telemetry
        completed = snapshot.tasks_completed
        persistent_blocks = sum(
            1 for item in telemetry.tasks if item.blocked_by_prior_progress
        )
        if snapshot.evidence_sequence <= 0:
            return EvolutionEligibility(False, "no_evidence_sequence")
        if completed < 3:
            return EvolutionEligibility(False, "minimum_dwell")
        if persistent_blocks < 2:
            return EvolutionEligibility(False, "insufficient_persistence")
        return EvolutionEligibility(True, "evidence_eligible")


class _EvidenceDiagnosis(DiagnosisPort):
    def __init__(
        self,
        source: EvolutionSessionSource,
        architecture: MemoryArchitectureSpec | None,
    ) -> None:
        self._source = source
        self._architecture = architecture

    def diagnose(self) -> ArchitectureObservationReport:
        snapshot = self._source.snapshot()
        telemetry = snapshot.telemetry
        summary = (
            f"generation={snapshot.generation};tasks={snapshot.tasks_completed};"
            f"queries={len(telemetry.queries)};incidents={len(telemetry.incidents)}"
        )
        profiles: list[NodeObservationProfile] = []
        if self._architecture is not None:
            for node in self._architecture.nodes:
                row = telemetry.node_stats.get(node.node_id, {})
                profiles.append(
                    NodeObservationProfile(
                        node_id=node.node_id,
                        selected_count=int(row.get("selected_count", 0)),
                        result_count=int(row.get("result_count", 0)),
                        query_count=int(row.get("query_count", 0)),
                        empty_result_count=int(row.get("empty_result_count", 0)),
                        update_count=int(row.get("update_count", 0)),
                        records_added=int(row.get("records_added", 0)),
                        records_removed=int(row.get("records_removed", 0)),
                    )
                )
        pair_counts: Counter[tuple[str, str]] = Counter()
        for query in telemetry.queries:
            selected = tuple(sorted(set(query.selected_nodes)))
            pair_counts.update(combinations(selected, 2))
        pairs = tuple(
            NodePairObservation(
                pair_id=f"pair:{left}:{right}",
                left_node_id=left,
                right_node_id=right,
                co_select_count=count,
            )
            for (left, right), count in sorted(pair_counts.items())
        )
        clusters = tuple(
            UnresolvedIntentCluster(
                cluster_id=item.slice_id,
                support=item.support,
                examples=item.examples,
            )
            for item in AutomaticSliceDiscovery().discover(telemetry.incidents)
        )
        return ArchitectureObservationReport(
            generation=snapshot.generation,
            neutral_summary=summary,
            evidence_refs=(
                f"sem.evidence-sequence:{snapshot.evidence_sequence}",
                f"sem.evidence-digest:{snapshot.evidence_digest}",
            ),
            architecture=self._architecture,
            node_profiles=tuple(profiles),
            pairs=pairs,
            incident_counts=tuple(
                sorted(Counter(item.kind.value for item in telemetry.incidents).items())
            ),
            unresolved_intent_clusters=clusters,
        )


class _ExplicitProposalSynthesis(SynthesisPort):
    def __init__(self, proposal: StructuralProposalPort | None) -> None:
        self._proposal = proposal

    def propose(self, report: ArchitectureObservationReport) -> StructuralIntent:
        if self._proposal is None:
            return StructuralIntent(
                EditKind.NO_EDIT,
                "no typed structural proposal port is bound",
                payload={"evidence_refs": report.evidence_refs},
            )
        proposed = self._proposal.propose(report)
        if proposed is None:
            return StructuralIntent(
                EditKind.NO_EDIT,
                "bound proposal authority produced no edit",
                payload={"evidence_refs": report.evidence_refs},
            )
        if not proposed.rationale.strip():
            raise ValueError("structural proposal rationale is required")
        return proposed


class _NoEditProposalAuthority:
    """Explicit conservative proposal authority for plumbing-only runs."""

    def propose(self, report: ArchitectureObservationReport) -> StructuralIntent | None:
        del report
        return None


class RuleBasedProposalAuthority:
    """Deterministic, ontology-free RuleBasedEvolver proposal policy."""

    def propose(self, report: ArchitectureObservationReport) -> StructuralIntent | None:
        if not report.unresolved_intent_clusters:
            return StructuralIntent(
                EditKind.NO_EDIT,
                "rule policy found no unresolved intent cluster",
                payload={"evidence_refs": report.evidence_refs},
            )
        return StructuralIntent(
            EditKind.NO_EDIT,
            "rule policy requires an explicit typed edit template; no unsafe schema invention",
            payload={
                "evidence_refs": report.evidence_refs,
                "cluster_ids": tuple(item.cluster_id for item in report.unresolved_intent_clusters),
            },
        )


class _VerifiedCompiler(CompilerPort):
    def __init__(self) -> None:
        self._compiler = StructuralCompiler(_build_target)
        self._verifier = OperationalVerifier()

    def compile(self, intent: StructuralIntent, base_generation: str):
        candidate = self._compiler.compile(intent, base_generation)
        self._verifier.verify(candidate)
        if canonical_digest(candidate.target_spec) != candidate.target_spec_digest:
            raise ValueError("compiled candidate target digest is not authoritative")
        return candidate


class EvolutionBindingError(RuntimeError):
    """A scientific evolution stage was reached without its authority port."""

    code = "SEM_EVOLUTION_BINDING_REQUIRED"


class _FailClosedEvaluator(EvaluatorPort):
    def evaluate(self, candidate) -> EvaluationProof:
        raise EvolutionBindingError(
            "SEM evolution evaluator is not bound; inject a paired evaluator before emitting an edit"
        )


class _EvidenceAcceptance(AcceptancePort):
    def accept(self, intent: StructuralIntent, proof: EvaluationProof) -> bool:
        del intent
        return bool(proof.comparability.valid and proof.metrics)


class _FailClosedAdoption(AdoptionPort):
    def adopt(self, candidate, proof) -> str:
        del candidate, proof
        raise EvolutionBindingError(
            "SEM evolution adoption is not bound; inject a session adoption authority before adoption"
        )


def _build_target(
    base_generation: str,
    edits: tuple[PrimitiveEdit, ...],
    intent: StructuralIntent,
):
    """Compile a typed architecture edit instead of selecting a fixed preset.

    The generic evolution compiler carries a project-owned ``ArchitectureEdit``
    in the intent payload.  The project architecture compiler is the sole
    authority that turns it into a validated target specification.
    """

    del base_generation, edits
    payload = intent.payload
    architecture_edit = payload.get("architecture_edit") if isinstance(payload, dict) else None
    if not isinstance(
        architecture_edit,
        (CreateNodeEdit, RetireNodeEdit, SplitNodeEdit, MergeNodesEdit),
    ):
        raise EvolutionBindingError(
            "SEM structural intent must carry a typed ArchitectureEdit payload"
        )
    current = payload.get("architecture") if isinstance(payload, dict) else None
    if not isinstance(current, MemoryArchitectureSpec):
        raise EvolutionBindingError(
            "SEM structural intent must carry the observed current architecture"
        )
    target = ArchitectureCompiler().compile_edit(current, architecture_edit)
    contracts = tuple(
        MaterializationContract(node.node_id, node.selector, node.transform)
        for node in target.nodes
    )
    return target, contracts


@dataclass(frozen=True, slots=True)
class SemPaperEvolutionBindings:
    """Replaceable provider set for the project evolution graph."""

    proposal: StructuralProposalPort = field(default_factory=_NoEditProposalAuthority)
    evaluator: EvolutionEvaluationPort = field(default_factory=_FailClosedEvaluator)
    adoption: EvolutionAdoptionPort = field(default_factory=_FailClosedAdoption)
    reconciliation: EvolutionReconciliationPort = field(
        default_factory=ConservativeEvolutionReconciler
    )

    @property
    def complete(self) -> bool:
        """Whether every scientific evolution authority is explicitly bound."""

        return all(
            item is not None
            for item in (self.proposal, self.evaluator, self.adoption, self.reconciliation)
        )

    @property
    def scientific_ready(self) -> bool:
        """Whether this binding can accept and publish a real structural edit."""

        return not any(
            isinstance(
                item,
                (
                    _NoEditProposalAuthority,
                    _FailClosedEvaluator,
                    _FailClosedAdoption,
                    ConservativeEvolutionReconciler,
                ),
            )
            for item in (self.proposal, self.evaluator, self.adoption, self.reconciliation)
        )

    @property
    def binding_digest(self) -> str:
        def identity(value: object | None) -> str | None:
            if value is None:
                return None
            cls = type(value)
            return f"{cls.__module__}.{cls.__qualname__}"

        return canonical_digest(
            {
                "proposal": identity(self.proposal),
                "evaluator": identity(self.evaluator),
                "adoption": identity(self.adoption),
                "reconciliation": identity(self.reconciliation),
            }
        )

    def require_complete(self) -> None:
        if not self.complete:
            missing = tuple(
                name
                for name, value in (
                    ("proposal", self.proposal),
                    ("evaluator", self.evaluator),
                    ("adoption", self.adoption),
                    ("reconciliation", self.reconciliation),
                )
                if value is None
            )
            raise EvolutionBindingError(
                "SEM scientific evolution requires explicit bindings for: "
                + ", ".join(missing)
            )

    def require_scientific_ready(self) -> None:
        self.require_complete()
        if not self.scientific_ready:
            raise EvolutionBindingError(
                "SEM scientific evolution requires non-fail-closed proposal, "
                "evaluation, adoption and reconciliation authorities"
            )


def build_sem_paper_evolution_factory(
    bindings: SemPaperEvolutionBindings | None = None,
    *,
    architecture: MemoryArchitectureSpec | None = None,
    allow_fail_closed: bool = False,
) -> SessionEvolutionFactory:
    """Compose the SEM pipeline with explicit, session-scoped stage factories.

    Scientific composition is strict by default.  A fail-closed graph is
    available only when the caller explicitly marks the run as a non-claim
    conformance run; this prevents placeholder providers from being mistaken
    for a complete self-evolution implementation.
    """

    bound = bindings or SemPaperEvolutionBindings()
    if allow_fail_closed:
        bound.require_complete()
    else:
        bound.require_scientific_ready()
    stages = EvolutionStageFactories(
        eligibility=lambda source: _EvidenceEligibility(source),
        diagnosis=lambda source: _EvidenceDiagnosis(source, architecture),
        synthesis=lambda: _ExplicitProposalSynthesis(bound.proposal),
        compiler=_VerifiedCompiler,
        evaluator=lambda: bound.evaluator,
        acceptance=_EvidenceAcceptance,
        adoption=lambda authority: bound.adoption,
        reconciliation=lambda: bound.reconciliation,
    )
    return PipelineSessionEvolutionFactory(stages)


def build_rule_based_evolution_factory(
    *,
    architecture: MemoryArchitectureSpec | None = None,
) -> SessionEvolutionFactory:
    """Compose deterministic RuleBasedEvolver through the same stage graph."""

    return build_sem_paper_evolution_factory(
        SemPaperEvolutionBindings(proposal=RuleBasedProposalAuthority()),
        architecture=architecture,
        allow_fail_closed=True,
    )


def build_nonclaim_evolution_factory(
    *,
    architecture: MemoryArchitectureSpec | None = None,
) -> SessionEvolutionFactory:
    """Explicit fail-closed factory for portability/conformance executions."""

    return build_sem_paper_evolution_factory(
        SemPaperEvolutionBindings(),
        architecture=architecture,
        allow_fail_closed=True,
    )


__all__ = [
    "EvolutionAdoptionPort",
    "EvolutionBindingError",
    "EvolutionEvaluationPort",
    "RuleBasedProposalAuthority",
    "SemPaperEvolutionBindings",
    "StructuralProposalPort",
    "build_rule_based_evolution_factory",
    "build_nonclaim_evolution_factory",
    "build_sem_paper_evolution_factory",
]
