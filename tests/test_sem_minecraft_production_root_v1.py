from __future__ import annotations

from types import SimpleNamespace

from projects.sem_paper.composition import (
    SemPaperMinecraftProductionRoot,
    build_seed_x_candidate,
    compose_sem_paper_minecraft_production_root,
)
from projects.sem_paper.composition.minecraft_workload import (
    MinecraftTaskSpec,
    minecraft_task_manifest_digest,
)
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from research_platform.platform.kernel import ExecutionContext
from research_platform.experimentation.run.api import ExperimentRunSpec
from research_platform.experimentation.study.api import (
    StudyProtocol,
    StudyVariantSpec,
    VariantKind,
)
from research_platform.experimentation.run.composition import build_default_experiment_run_application
from research_platform.platform.kernel import canonical_digest


def test_production_root_freezes_the_unique_paired_graph_without_opening_resources() -> None:
    composition = SimpleNamespace(bindings=SimpleNamespace(fixed_memory=object(), candidate_method_materializer=None))
    protocol = StudyProtocol(
        study_id="study-1",
        workload_id="workload-1",
        variants=(
            StudyVariantSpec("control", VariantKind.CONTROL, "fixed", canonical_digest("fixed")),
            StudyVariantSpec("candidate", VariantKind.TREATMENT, "candidate", canonical_digest("candidate")),
        ),
        repetitions=1,
        seed_schedule_digest=canonical_digest("seed"),
        metric_names=("success_rate",),
        task_manifest_digest=minecraft_task_manifest_digest((
            MinecraftTaskSpec("task-1", "collection", "collect wood"),
        )),
    )
    run_executor = build_default_experiment_run_application(object())
    run_spec = ExperimentRunSpec(
        run_id="run-1",
        project_id="sem-paper-1",
        experiment_id="sem-paper-minecraft",
        study_id=protocol.study_id,
        execution_profile="test",
        task_manifest_digest=protocol.task_manifest_digest,
        seed_schedule_digest=protocol.seed_schedule_digest,
        repetitions=protocol.repetitions,
        artifact_root="C:/runs/run-1",
        environment_identity_digest=canonical_digest("minecraft-test"),
    )
    root = compose_sem_paper_minecraft_production_root(
        composition=composition,
        run_spec=run_spec,
        world_cuts=object(),
        branch_runtime_factory=object(),
        request_factory=object(),
        planner_factory=object(),
        observation_sink_factory=object(),
        tasks=(MinecraftTaskSpec("task-1", "collection", "collect wood"),),
        context=ExecutionContext("run-1", "trace-1", "span-1"),
        workload_id_factory=lambda role, branch: f"{role.value}:workload",
        session_id="paper-session",
        branch_id_factory=lambda role, repetition: f"{role.value}-rep-{repetition}-branch",
        destination_factory=lambda branch_id: f"C:/mc/{branch_id}",
        study_protocol=protocol,
        run_executor=run_executor,
        candidate=build_seed_x_candidate(),
    )

    assert isinstance(root, SemPaperMinecraftProductionRoot)
    assert root.composition is composition
    assert root.workload_executor.bindings is root.workload_bindings
    assert root.study_unit_executor is not None
    assert root.run_executor is not None
