from __future__ import annotations

from research_platform.experimentation.study.api import (
    StudyProtocol,
    StudyVariantSpec,
    VariantKind,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.platform.kernel import JsonInput
from research_platform.experimentation.study.api import ExperimentPlan, VariantBinding


SEM_PAPER_METRIC_NAMES = (
    "success_rate",
    "utility_mean",
    "steps_total",
    "duration_s_total",
    "memory_queries_total",
    "task_failed_total",
    "task_blocked_total",
)

CORE6_REPETITIONS = 12

CORE6_VARIANTS = (
    ("Fixed-C", VariantKind.CONTROL, "FixedSeed", "Seed-C"),
    ("Rule-C", VariantKind.TREATMENT, "RuleBasedEvolver", "Seed-C"),
    ("Self-C", VariantKind.TREATMENT, "SelfEvolve", "Seed-C"),
    ("Fixed-X", VariantKind.CONTROL, "FixedSeed", "Seed-X"),
    ("Rule-X", VariantKind.TREATMENT, "RuleBasedEvolver", "Seed-X"),
    ("Self-X", VariantKind.TREATMENT, "SelfEvolve", "Seed-X"),
)


def build_sem_paper_study_protocol(
    *,
    study_id: str,
    workload_id: str,
    task_manifest_digest: str,
    seed_identity: JsonInput,
    fixed_configuration: JsonInput,
    candidate_configuration: JsonInput,
    repetitions: int | None = None,
    matrix_profile: str = "paired-conformance",
) -> StudyProtocol:
    """Create a typed protocol shared by MC and non-MC adapters.

    The reusable helper defaults to the small non-claim conformance profile;
    every production entrypoint selects ``matrix_profile="core-6"``
    explicitly.  The protocol declares only scientific variants and metric
    identity; environments and method providers are injected by adapters.
    """

    if not task_manifest_digest.strip():
        raise ValueError("SEM Paper study protocol requires a task manifest digest")
    if matrix_profile == "core-6":
        variants = tuple(
            StudyVariantSpec(
                variant_id=variant_id,
                kind=kind,
                implementation_id=f"sem-paper.{implementation}",
                configuration_digest=canonical_digest({"seed": seed, "configuration": fixed_configuration if implementation == "FixedSeed" else candidate_configuration}),
                budget_tier="core",
            )
            for variant_id, kind, implementation, seed in CORE6_VARIANTS
        )
        budget_tiers = ("core",)
        repetitions = CORE6_REPETITIONS if repetitions is None else repetitions
    elif matrix_profile == "paired-conformance":
        variants = (
            StudyVariantSpec("control", VariantKind.CONTROL, "sem-paper.fixed-memory", canonical_digest(fixed_configuration)),
            StudyVariantSpec("candidate", VariantKind.TREATMENT, "sem-paper.candidate-memory", canonical_digest(candidate_configuration)),
        )
        budget_tiers = ("standard",)
        repetitions = 1 if repetitions is None else repetitions
    else:
        raise ValueError(f"unknown matrix profile: {matrix_profile}")
    return StudyProtocol(
        study_id=study_id,
        workload_id=workload_id,
        variants=variants,
        repetitions=repetitions,
        seed_schedule_digest=canonical_digest(seed_identity),
        metric_names=SEM_PAPER_METRIC_NAMES,
        task_manifest_digest=task_manifest_digest,
        budget_tiers=budget_tiers,
    )


def compile_sem_paper_experiment_plan(protocol: StudyProtocol) -> ExperimentPlan:
    """Compile every declared arm into an explicit runtime binding."""
    bindings = tuple(
        VariantBinding(
            variant=item,
            seed_id=(
                f"Seed-{item.variant_id.rsplit('-', 1)[-1]}"
                if item.variant_id.rsplit("-", 1)[-1] in {"C", "X"}
                else item.variant_id
            ),
            provider_id=item.implementation_id,
            ablation_policy_id="none",
            comparator_role="primary" if item.kind is not VariantKind.EXTERNAL_BASELINE else "external",
        )
        for item in protocol.variants
    )
    return ExperimentPlan.compile(protocol, bindings)


__all__ = [
    "CORE6_REPETITIONS",
    "CORE6_VARIANTS",
    "SEM_PAPER_METRIC_NAMES",
    "build_sem_paper_study_protocol",
    "compile_sem_paper_experiment_plan",
]
