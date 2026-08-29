from __future__ import annotations

from dataclasses import dataclass, replace

from projects.sem_paper.composition.candidate_method import (
    SemPaperVariantMethodEndpointFactory,
    build_seed_candidate,
    validate_plan_provider_closure,
)
from projects.sem_paper.composition.evolution import RuleBasedProposalAuthority
from projects.sem_paper.composition.minecraft_agent import SemMethodAgentMemoryAdapter
from projects.sem_paper.composition.scientific_metrics import SemPaperScientificMetricProvider
from projects.sem_paper.composition.study import (
    build_sem_paper_confirmatory_protocol,
    compile_sem_paper_experiment_plan,
    is_confirmatory_protocol,
)
from projects.sem_paper.composition.candidate_method import build_seed_x_candidate
from projects.sem_paper.method.self_evolving_memory.architecture import (
    SemPaperArchitecturePreset,
    build_sem_paper_architecture,
)
from projects.sem_paper.method.self_evolving_memory.evolution import (
    ArchitectureObservationReport,
    EditKind,
    NodeObservationProfile,
)
from research_platform.experimentation.study.api import (
    StudyMatrixExecutionReport,
    StudyMetricObservation,
)
from research_platform.experimentation.study.runtime.protocol import DeterministicStudyAssignment
from research_platform.participant.agent.api import AgentGoal, AgentObservation
from research_platform.participant.method.api import MethodIdentity, RecallResult
from research_platform.platform.kernel import ExecutionContext, canonical_digest


_DIGEST = "a" * 64


@dataclass
class _Endpoint:
    name: str

    @property
    def identity(self):
        return MethodIdentity("sem", "1", "1", "1", canonical_digest(self.name))

    @property
    def binding_digest(self):
        return canonical_digest({"endpoint": self.name})


class _Materializer:
    def __init__(self, prefix: str, seen: list[str] | None = None) -> None:
        self.prefix = prefix
        self.seen = seen

    def materialize(self, candidate):
        if self.seen is not None:
            self.seen.append(candidate.candidate_id)
        return _Endpoint(f"{self.prefix}:{candidate.target_spec_digest}")


class _Method:
    def __init__(self) -> None:
        self.requests = []

    def recall(self, request):
        self.requests.append(request)
        return RecallResult("SEM CONTEXT", "generation-sem", ("artifact://memory",))


def _core_plan(*, repetitions: int = 2):
    protocol = build_sem_paper_confirmatory_protocol(
        study_id="sem-integrity",
        workload_id="sem-integrity-workload",
        task_manifest_digest=_DIGEST,
        seed_identity={"seed": 1},
        fixed_configuration={"fixed": True},
        candidate_configuration={"candidate": True},
    )
    if repetitions != protocol.repetitions:
        protocol = replace(protocol, repetitions=repetitions)
        assert not is_confirmatory_protocol(protocol)
    return compile_sem_paper_experiment_plan(protocol)


def test_fixed_seed_controls_resolve_to_distinct_seed_endpoints() -> None:
    plan = _core_plan()
    factory = SemPaperVariantMethodEndpointFactory(
        fixed_endpoint=_Endpoint("fixed-c"),
        fixed_endpoints_by_seed={
            "Seed-C": _Endpoint("fixed-c"),
            "Seed-X": _Endpoint("fixed-x"),
        },
        rule_based_materializer=_Materializer("rule"),
        self_evolving_materializer=_Materializer("self"),
    )
    identities = validate_plan_provider_closure(
        plan=plan,
        factory=factory,
        candidate=build_seed_x_candidate(),
    )
    fixed = {item.seed_id: item for item in identities if item.provider_id.endswith("FixedSeed")}
    assert fixed["Seed-C"].endpoint_binding_digest != fixed["Seed-X"].endpoint_binding_digest
    assert fixed["Seed-C"].endpoint_artifact_digest != fixed["Seed-X"].endpoint_artifact_digest


def test_provider_preflight_uses_the_same_seed_candidate_identity_per_arm() -> None:
    plan = _core_plan()
    seen: list[str] = []
    factory = SemPaperVariantMethodEndpointFactory(
        fixed_endpoint=_Endpoint("fixed-c"),
        fixed_endpoints_by_seed={
            "Seed-C": _Endpoint("fixed-c"),
            "Seed-X": _Endpoint("fixed-x"),
        },
        rule_based_materializer=_Materializer("rule", seen),
        self_evolving_materializer=_Materializer("self", seen),
    )
    validate_plan_provider_closure(
        plan=plan,
        factory=factory,
        candidate=build_seed_x_candidate(base_generation="generation-7"),
        candidate_factory=lambda binding: build_seed_candidate(
            binding.seed_id,
            base_generation="generation-7",
        ),
    )
    assert seen == [
        "sem-paper:seed-c-v018",
        "sem-paper:seed-c-v018",
        "sem-paper:seed-x-v018",
        "sem-paper:seed-x-v018",
    ]


def test_cognition_memory_adapter_calls_bound_method_session() -> None:
    method = _Method()
    memory = SemMethodAgentMemoryAdapter(method)
    context = ExecutionContext("run", "trace", "span", task_id="task")
    goal = AgentGoal("task", "find iron")
    observation = AgentObservation("obs", "world-g1", {"inventory": {"iron": 0}})
    recalled = memory.recall(goal, observation, context)
    assert method.requests
    assert method.requests[0].intent.startswith("find iron")
    assert recalled.context_text == "SEM CONTEXT"
    assert recalled.generation == "generation-sem"
    assert recalled.query_id.startswith("sem-method-query:")


def test_primary_statistics_use_matched_environment_unit_not_seed_rows() -> None:
    plan = _core_plan(repetitions=2)
    # Self-vs-Fixed deltas by environment unit:
    # rep0: C=1, X=3 -> unit effect 2
    # rep1: C=5, X=1 -> unit effect 3
    values = {
        ("Fixed-C", 0): 0.0, ("Self-C", 0): 1.0,
        ("Fixed-X", 0): 0.0, ("Self-X", 0): 3.0,
        ("Fixed-C", 1): 0.0, ("Self-C", 1): 5.0,
        ("Fixed-X", 1): 0.0, ("Self-X", 1): 1.0,
    }
    for rep in range(2):
        values[("Rule-C", rep)] = 0.25 + rep
        values[("Rule-X", rep)] = 0.50 + rep
    observations = tuple(
        StudyMetricObservation(
            assignment,
            (
                ("utility_mean", values[(assignment.variant_id, assignment.repetition)]),
                ("task_blocked_total", 0.0),
            ),
        )
        for assignment in DeterministicStudyAssignment().assignments(plan.protocol)
    )
    report = StudyMatrixExecutionReport(
        plan.protocol_digest,
        observations,
        (),
        binding_digest=plan.binding_digest,
        plan_digest=plan.plan_digest,
    )
    statistics = SemPaperScientificMetricProvider().compute_statistics(plan=plan, report=report)
    primary = next(item for item in statistics.comparisons if item.comparison_id == "SelfEvolve_vs_FixedSeed")
    assert primary.sample_count == 2
    assert primary.estimate == 2.5
    # Unit effects [2, 3] -> sample variance .5, SE=sqrt(.5/2)=.5.
    assert abs(primary.standard_error - 0.5) < 1e-12


def test_lifetime_estimands_use_matched_units_and_lpi_is_probability_of_improvement() -> None:
    plan = _core_plan(repetitions=2)
    # rep0 matched delta = (+2 + +2) / 2 = +2
    # rep1 matched delta = (-1 + -3) / 2 = -2
    # Therefore LTE=0 and LPI=P(delta>0)=1/2.  This specifically guards
    # against the former (incorrect) mean-relative-effect implementation.
    values = {
        ("Fixed-C", 0): 1.0, ("Self-C", 0): 3.0,
        ("Fixed-X", 0): 2.0, ("Self-X", 0): 4.0,
        ("Fixed-C", 1): 10.0, ("Self-C", 1): 9.0,
        ("Fixed-X", 1): 20.0, ("Self-X", 1): 17.0,
    }
    for rep in range(2):
        values[("Rule-C", rep)] = 1.5 + rep
        values[("Rule-X", rep)] = 2.5 + rep
    observations = tuple(
        StudyMetricObservation(
            assignment,
            (("utility_mean", values[(assignment.variant_id, assignment.repetition)]),
             ("task_blocked_total", 0.0)),
        )
        for assignment in DeterministicStudyAssignment().assignments(plan.protocol)
    )
    report = StudyMatrixExecutionReport(
        plan.protocol_digest,
        observations,
        (),
        binding_digest=plan.binding_digest,
        plan_digest=plan.plan_digest,
    )
    metrics = SemPaperScientificMetricProvider().compute(plan=plan, report=report)
    result = dict(metrics.values)
    assert result["LTE_SR"] == 0.0
    assert result["LPI"] == 0.5
    # Self matched utilities: rep0=3.5, rep1=13 -> CLU mean=8.25.
    assert result["CLU"] == 8.25


def test_rule_based_evolver_can_emit_legal_nontrivial_retire() -> None:
    architecture = build_sem_paper_architecture(SemPaperArchitecturePreset.C)
    report = ArchitectureObservationReport(
        generation="g0",
        neutral_summary="sufficient neutral telemetry",
        evidence_refs=("evidence://telemetry",),
        architecture=architecture,
        node_profiles=(
            NodeObservationProfile(
                node_id="mem_world",
                query_count=10,
                selected_count=0,
                result_count=0,
            ),
        ),
    )
    intent = RuleBasedProposalAuthority().propose(report)
    assert intent is not None
    assert intent.edit is EditKind.RETIRE
    assert isinstance(intent.payload, dict)
    assert intent.payload["architecture"] is architecture
    assert intent.payload["architecture_edit"].target_node_id == "mem_world"


def test_run_local_auxiliary_samples_finalize_with_exact_provenance(tmp_path) -> None:
    from projects.sem_paper.composition.scientific_metrics import (
        DirectoryScientificAuxiliarySampleStore,
        SCIENTIFIC_AUXILIARY_SAMPLE_SCHEMA_VERSION,
        ScientificAuxiliarySampleEvidence,
        finalize_scientific_auxiliary_evidence,
        load_scientific_auxiliary_evidence,
    )

    plan = _core_plan(repetitions=2)
    source_digest = "b" * 64
    store = DirectoryScientificAuxiliarySampleStore(tmp_path / "samples")
    for seed_id, tdp, elce, hpef, gag in (
        ("Seed-C", 0.2, 0.1, 0.5, 0.1),
        ("Seed-X", 0.4, 0.3, 1.0, 0.3),
    ):
        store.publish(
            ScientificAuxiliarySampleEvidence(
                schema_version=SCIENTIFIC_AUXILIARY_SAMPLE_SCHEMA_VERSION,
                sample_id=f"sample:{seed_id}",
                run_id="run-1",
                seed_id=seed_id,
                source_tree_digest=source_digest,
                plan_digest=plan.plan_digest,
                trajectory_divergence=tdp,
                held_out_causal_effect=elce,
                held_out_positive_edit_fraction=hpef,
                gate_to_audit_generalization_gap=gag,
                evidence_refs=(f"evidence://{seed_id}",),
            )
        )
    target = tmp_path / "final.json"
    finalized = finalize_scientific_auxiliary_evidence(
        plan=plan,
        source_tree_digest=source_digest,
        run_id="run-1",
        sample_store=store,
        output_path=target,
    )
    loaded = load_scientific_auxiliary_evidence(target)
    assert loaded.digest == finalized.digest
    assert dict(loaded.values) == {
        "ELCE": 0.2,
        "GAG": 0.2,
        "HPEF": 0.75,
        "TDP": 0.30000000000000004,
    }
    assert loaded.evidence_refs == ("evidence://Seed-C", "evidence://Seed-X")


def test_operator_can_load_scientific_evolution_bindings_from_trusted_factory(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    from projects.sem_paper.composition.evolution import SemPaperEvolutionBindings
    from scripts.sem_paper_minecraft_application import _load_evolution_bindings

    class _Proposal:
        def propose(self, report):
            return None

    class _Evaluator:
        def evaluate(self, candidate):
            raise AssertionError("not executed by loader")

    class _Adoption:
        def adopt(self, candidate, proof):
            raise AssertionError("not executed by loader")

    class _Reconciliation:
        def reconcile(self, **kwargs):
            raise AssertionError("not executed by loader")

    bindings = SemPaperEvolutionBindings(
        proposal=_Proposal(),
        evaluator=_Evaluator(),
        adoption=_Adoption(),
        reconciliation=_Reconciliation(),
    )
    module_name = "_sem_test_evolution_bindings"
    monkeypatch.setitem(
        sys.modules,
        module_name,
        SimpleNamespace(factory=lambda inputs: bindings),
    )
    assert _load_evolution_bindings(f"{module_name}:factory", object()) is bindings
    assert bindings.scientific_ready
