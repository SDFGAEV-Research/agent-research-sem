from __future__ import annotations

from research_platform.experimentation.study.api import (
    StudyProtocol,
    StudyVariantSpec,
    VariantKind,
)
from research_platform.platform.kernel import canonical_digest


SEM_PAPER_METRIC_NAMES = (
    "success_rate",
    "utility_mean",
    "steps_total",
    "duration_s_total",
    "memory_queries_total",
    "task_failed_total",
    "task_blocked_total",
)


def build_sem_paper_study_protocol(
    *,
    study_id: str,
    workload_id: str,
    task_manifest_digest: str,
    seed_identity: object,
    fixed_configuration: object,
    candidate_configuration: object,
    repetitions: int = 1,
) -> StudyProtocol:
    """Create the frozen paired protocol shared by MC and non-MC adapters.

    The protocol declares only scientific variants and metric identity.  It
    does not select an environment, start a model, or decide how a candidate
    is materialized; those are injected by the respective adapters.
    """

    if not task_manifest_digest.strip():
        raise ValueError("SEM Paper study protocol requires a task manifest digest")
    return StudyProtocol(
        study_id=study_id,
        workload_id=workload_id,
        variants=(
            StudyVariantSpec(
                variant_id="control",
                kind=VariantKind.CONTROL,
                implementation_id="sem-paper.fixed-memory",
                configuration_digest=canonical_digest(fixed_configuration),
            ),
            StudyVariantSpec(
                variant_id="candidate",
                kind=VariantKind.TREATMENT,
                implementation_id="sem-paper.candidate-memory",
                configuration_digest=canonical_digest(candidate_configuration),
            ),
        ),
        repetitions=repetitions,
        seed_schedule_digest=canonical_digest(seed_identity),
        metric_names=SEM_PAPER_METRIC_NAMES,
        task_manifest_digest=task_manifest_digest,
        budget_tiers=("standard",),
    )


__all__ = ["SEM_PAPER_METRIC_NAMES", "build_sem_paper_study_protocol"]
