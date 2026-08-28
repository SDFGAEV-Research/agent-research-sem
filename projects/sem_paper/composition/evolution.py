"""SEM production evolution composition.

This module is the project-owned composition root for the seven evolution
stages.  Stage implementations remain replaceable ports: the default graph
is evidence-bound and fail-closed until an outer runtime supplies a structural
proposal, paired evaluator, and adoption authority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
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
    MemoryNodeDraft,
    RetireNodeEdit,
    SplitChildDraft,
    SplitNodeEdit,
)
from projects.sem_paper.method.self_evolving_memory.architecture.contracts import (
    PredicateAtom,
    PredicateOp,
    PrimitiveType,
    RecordSelector,
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

    _MIN_USAGE_FOR_RETIRE = 8
    _MIN_COSELECT_FOR_MERGE = 8
    _MIN_QUERIES_FOR_SPLIT = 12

    @staticmethod
    def _payload(
        report: ArchitectureObservationReport,
        architecture_edit,
        **extra: object,
    ) -> dict[str, object]:
        return {
            "architecture": report.architecture,
            "architecture_edit": architecture_edit,
            "evidence_refs": report.evidence_refs,
            **extra,
        }

    @staticmethod
    def _merge_compatible(left, right) -> bool:
        return (
            left.selector is not None
            and right.selector is not None
            and left.selector.all_of == right.selector.all_of
            and left.selector.negated != right.selector.negated
            and left.scope == right.scope
            and left.mode == right.mode
            and left.schema == right.schema
            and left.primary_key == right.primary_key
            and left.sources == right.sources
            and left.transform == right.transform
        )

    def propose(self, report: ArchitectureObservationReport) -> StructuralIntent | None:
        architecture = report.architecture
        if architecture is None:
            return StructuralIntent(
                EditKind.NO_EDIT,
                "rule policy has no typed architecture to edit",
                payload={"evidence_refs": report.evidence_refs},
            )
        node_map = architecture.node_map()

        # MERGE: only complementary siblings with an identical structural
        # shape can be merged, and only after repeated co-selection.
        for pair in sorted(report.pairs, key=lambda item: (-item.co_select_count, item.pair_id)):
            if pair.co_select_count < self._MIN_COSELECT_FOR_MERGE:
                break
            left = node_map.get(pair.left_node_id)
            right = node_map.get(pair.right_node_id)
            if left is None or right is None or not self._merge_compatible(left, right):
                continue
            edit = MergeNodesEdit(
                "MERGE_NODES",
                left.node_id,
                right.node_id,
                f"{left.label}Merged",
                "Merge repeatedly co-selected complementary partitions without changing their typed data contract.",
                left.access | right.access,
            )
            return StructuralIntent(
                EditKind.MERGE,
                "deterministic rule merged repeatedly co-selected compatible sibling partitions",
                payload=self._payload(report, edit, pair_id=pair.pair_id),
            )

        # RETIRE: a leaf that has had enough opportunities but has never been
        # selected or returned a result contributes no unique serving value.
        if len(architecture.nodes) > 2:
            for profile in sorted(report.node_profiles, key=lambda item: item.node_id):
                if (
                    profile.query_count >= self._MIN_USAGE_FOR_RETIRE
                    and profile.selected_count == 0
                    and profile.result_count == 0
                    and not architecture.downstream_ids(profile.node_id)
                ):
                    edit = RetireNodeEdit("RETIRE_NODE", profile.node_id)
                    return StructuralIntent(
                        EditKind.RETIRE,
                        "deterministic rule retired an unused leaf after sufficient query exposure",
                        payload=self._payload(report, edit, node_id=profile.node_id),
                    )

        # SPLIT: repeated empty retrievals plus an unresolved cluster provide a
        # typed, evidence-backed partition cue.  The rule uses an existing
        # scalar text/category field; the evaluator remains authoritative for
        # whether the proposal improves the treatment.
        if report.unresolved_intent_clusters:
            cluster = sorted(
                report.unresolved_intent_clusters,
                key=lambda item: (-item.support, item.cluster_id),
            )[0]
            for profile in sorted(report.node_profiles, key=lambda item: item.node_id):
                if (
                    profile.query_count < self._MIN_QUERIES_FOR_SPLIT
                    or profile.empty_result_count * 2 < profile.query_count
                ):
                    continue
                node = node_map.get(profile.node_id)
                if node is None:
                    continue
                field = next(
                    (
                        item
                        for item in node.schema
                        if item.dtype.base in {PrimitiveType.TEXT, PrimitiveType.CATEGORY}
                    ),
                    None,
                )
                if field is None:
                    continue
                edit = SplitNodeEdit(
                    "SPLIT_NODE",
                    node.node_id,
                    RecordSelector((PredicateAtom(field.name, PredicateOp.EQ, cluster.cluster_id),)),
                    SplitChildDraft(
                        f"{node.label}Focused",
                        "Partition records matching the recurrent unresolved-intent cue.",
                        node.access,
                    ),
                    SplitChildDraft(
                        f"{node.label}Remainder",
                        "Retain the complementary records under the original typed contract.",
                        node.access,
                    ),
                )
                return StructuralIntent(
                    EditKind.SPLIT,
                    "deterministic rule split a high-miss node using a recurrent unresolved-intent cue",
                    payload=self._payload(report, edit, cluster_id=cluster.cluster_id),
                )

            # CREATE: if no safe split target exists, reuse the complete typed
            # contract of a grounded evidence-backed node.  This avoids schema
            # invention while still allowing RuleBased to propose structural
            # growth for a persistent unresolved cluster.
            source = next(
                (
                    node
                    for node in sorted(architecture.nodes, key=lambda item: item.node_id)
                    if node.sources
                ),
                None,
            )
            if source is not None:
                draft = MemoryNodeDraft(
                    label="UnresolvedIntentMemory",
                    purpose=(
                        "Store a separate evidence-backed view for recurrent unresolved intents; "
                        "the evaluator decides whether the additional node is useful."
                    ),
                    scope=source.scope,
                    mode=source.mode,
                    schema=source.schema,
                    primary_key=source.primary_key,
                    access=source.access,
                    sources=source.sources,
                    transform=source.transform,
                    selector=source.selector,
                )
                edit = CreateNodeEdit("CREATE_NODE", draft)
                return StructuralIntent(
                    EditKind.CREATE,
                    "deterministic rule created a grounded typed view for a persistent unresolved-intent cluster",
                    payload=self._payload(report, edit, cluster_id=cluster.cluster_id),
                )

        return StructuralIntent(
            EditKind.NO_EDIT,
            "rule policy found no deterministic structural edit meeting frozen evidence thresholds",
            payload={"evidence_refs": report.evidence_refs},
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
    bindings: SemPaperEvolutionBindings,
    *,
    architecture: MemoryArchitectureSpec | None = None,
) -> SessionEvolutionFactory:
    """Compose RuleBasedEvolver with the *same* scientific gate authorities.

    RuleBased is a comparator over proposal policy, not a plumbing-only arm.
    It therefore shares the paired evaluator, adoption authority and
    reconciliation authority with SelfEvolve while replacing only the
    structural proposal policy.  This prevents a deterministic rule edit from
    falling into the historical fail-closed evaluator/adoption placeholders.
    """

    bindings.require_scientific_ready()
    return build_sem_paper_evolution_factory(
        replace(bindings, proposal=RuleBasedProposalAuthority()),
        architecture=architecture,
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
