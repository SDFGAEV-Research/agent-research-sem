"""Execute the SEM portability-conformance study on a deterministic closed world.

This application deliberately makes no scientific superiority claim. It runs
the same Study, Workload, Method and evidence interfaces as the Minecraft root
against a checkpointable platform state-machine environment.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from collections.abc import Mapping
from uuid import uuid4

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from projects.sem_paper.composition import (
    ReferenceClosedWorldCompletion,
    ReferenceClosedWorldDynamics,
    ReferenceClosedWorldPlannerFactory,
    ReferenceClosedWorldState,
    SEMClosedWorldEvidenceFactory,
    SemPaperCandidateMethodMaterializer,
    SemPaperCompositionPorts,
    SemPaperNonMinecraftWorkloadPorts,
    build_seed_candidate,
    build_seed_x_candidate,
    build_sem_paper_study_protocol,
    compile_sem_paper_experiment_plan,
    compose_sem_paper,
    compose_sem_paper_non_minecraft_production_root,
    register_sem_paper_scope,
    reference_closed_world_spec,
)
from projects.sem_paper.method.self_evolving_memory import GroundedSemanticTransformer
from projects.sem_paper.composition.evolution import build_nonclaim_evolution_factory
from projects.sem_paper.composition.session_state import DurableSEMSessionStateFactory
from projects.sem_paper.method.self_evolving_memory.serving_providers import (
    build_deluxe_session_serving,
    build_hybrid_session_serving,
)
from projects.sem_paper.method.self_evolving_memory.typed_materialization import (
    build_sem_paper_live_deluxe_snapshot_factory,
)
from research_platform.experimentation.experiment.api import (
    ExperimentTaskSpec,
    validate_task_graph,
)
from research_platform.environment.runtime.composition import (
    StateMachineEnvironmentAssembly,
    compose_state_machine_environment,
)
from research_platform.experimentation.run.api import ExperimentRunSpec, RunArtifactKind
from research_platform.experimentation.run.composition import (
    build_default_experiment_run_application,
    build_directory_run_artifact_store,
)
from research_platform.experimentation.run.runtime import (
    DirectoryRunArtifactStore,
    JsonlRunDiagnostics,
    exception_chain,
)
from research_platform.observability.logging.composition import (
    LogQueryBinding,
    LogSinkBinding,
    compose_logging_system,
)
from research_platform.observability.logging.storage.runtime.jsonl import JsonlLogStore
from research_platform.observability.logging.storage.composition import build_jsonl_log_store
from research_platform.participant.method.composition import compose_default_method_system
from research_platform.platform.composition.platform_meta import build_durable_platform_meta
from research_platform.platform.kernel import ExecutionContext, canonical_digest, canonical_text
from research_platform.platform.composition.concurrency import build_execution_concurrency_runtime
from research_platform.platform.kernel.errors import describe_exception


class NonMinecraftExperimentConfigurationError(ValueError):
    """The closed-world conformance inputs are incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class NonMinecraftExperimentInputs:
    run_id: str
    output_dir: Path
    tasks_path: Path
    task_ids: tuple[str, ...]
    repetitions: int
    matrix_profile: str = "paired-conformance"


def parse_inputs(argv: list[str] | None = None) -> NonMinecraftExperimentInputs:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--tasks", type=Path, default=None)
    parser.add_argument("--task-ids", default="")
    parser.add_argument("--repetitions", type=int, default=12)
    parser.add_argument(
        "--matrix-profile",
        choices=("paired-conformance",),
        default="paired-conformance",
        help="non-claim portability/conformance profile; scientific Core-6 is Minecraft-only",
    )
    args = parser.parse_args(argv)
    if args.repetitions <= 0:
        raise NonMinecraftExperimentConfigurationError("repetitions must be positive")
    run_id = args.run_id.strip() or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid4().hex[:8]
    )
    output = (
        args.output_dir
        or _REPOSITORY_ROOT / "runs" / "sem_paper_non_minecraft" / run_id
    ).expanduser().resolve(strict=False)
    tasks = (
        args.tasks
        or _REPOSITORY_ROOT
        / "projects"
        / "sem_paper"
        / "experiments"
        / "manifests"
        / "closed_world_reference_v1.json"
    ).expanduser().resolve(strict=False)
    selected = tuple(value.strip() for value in args.task_ids.split(",") if value.strip())
    return NonMinecraftExperimentInputs(
        run_id,
        output,
        tasks,
        selected,
        args.repetitions,
        args.matrix_profile,
    )


def load_tasks(
    path: Path,
    selected_ids: tuple[str, ...] = (),
) -> tuple[ExperimentTaskSpec, ...]:
    if not path.is_file():
        raise NonMinecraftExperimentConfigurationError(f"task manifest is missing: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping) or not isinstance(document.get("tasks"), list):
            raise TypeError("task manifest must contain a task list")
        tasks = tuple(
            ExperimentTaskSpec(
                task_id=str(row["task_id"]),
                family=str(row["family"]),
                objective=str(row["objective"]),
                context=(
                    str(row.get("context", ""))
                    if isinstance(row.get("context", ""), str)
                    else canonical_text(row.get("context", {}))
                ),
                lineage_id=str(row.get("lineage_id", "")),
                depends_on_task_ids=tuple(
                    str(value) for value in row.get("depends_on_task_ids", ())
                ),
                retry_of_task_id=(
                    None
                    if row.get("retry_of_task_id") is None
                    else str(row["retry_of_task_id"])
                ),
                max_steps=int(row.get("max_steps", 12)),
                max_seconds=float(row.get("max_seconds", 180.0)),
            )
            for row in document["tasks"]
            if isinstance(row, Mapping)
        )
        if len(tasks) != len(document["tasks"]):
            raise TypeError("task manifest contains a non-mapping task")
        return validate_task_graph(tasks, selected_ids=selected_ids)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise NonMinecraftExperimentConfigurationError(
            f"task manifest validation failed: {exc}"
        ) from exc


class _ArtifactMethodObservationSink:
    def __init__(self, artifacts: DirectoryRunArtifactStore, name: str) -> None:
        self._artifacts = artifacts
        self._name = name

    def record(self, observation: object) -> None:
        self._artifacts.append_json(
            self._name,
            {"observation": observation},
            kind=RunArtifactKind.EVIDENCE,
        )


class _ObservationSinkFactory:
    def __init__(self, artifacts: DirectoryRunArtifactStore) -> None:
        self._artifacts = artifacts

    def create(self, *, role, repetition, variant_id=None):
        suffix = variant_id or role.value
        return _ArtifactMethodObservationSink(
            self._artifacts,
            f"method_observations/{suffix}_rep_{repetition}.jsonl",
        )


class _ReferenceEnvironmentFactory:
    """Outer-root binding of project dynamics to the platform runtime provider."""

    def __init__(self, assembly: StateMachineEnvironmentAssembly) -> None:
        self._assembly = assembly

    @property
    def environment_digest(self) -> str:
        return self._assembly.implementation.identity.artifact_digest

    def open(self, *, role, candidate, unit, assignment, context):
        del candidate, unit
        return self._assembly.runtime.open_session(
            self._assembly.implementation,
            session_id=(
                f"{context.run_id}:{role.value}:rep-{assignment.repetition}:closed-world"
            ),
            services={},
        )


def _compose_project(artifacts: DirectoryRunArtifactStore, *, task_group):
    meta = build_durable_platform_meta(artifacts.root / "platform")
    project_scope = register_sem_paper_scope(meta.scopes)
    log_store = build_jsonl_log_store(
        artifacts.root / "logs" / "events.jsonl",
        task_group=task_group,
    )
    log_digest = canonical_digest({"kind": "jsonl", "path": "logs/events.jsonl", "scope": "sem-paper"})
    logging = compose_logging_system(
        sink=LogSinkBinding(log_store, "sem-paper.jsonl-log-store.v1", log_digest),
        query=LogQueryBinding(log_store, "sem-paper.jsonl-log-store.v1", log_digest),
        planner=meta.capability_composition,
        scope=project_scope,
    )
    method_system = compose_default_method_system(
        planner=meta.capability_composition,
        scope=project_scope,
    )
    transformer = GroundedSemanticTransformer()
    state_factory = DurableSEMSessionStateFactory(artifacts.root / "sem-session-state")
    # This application is explicitly portability-only. Do not label a
    # fail-closed/no-edit stage graph as a scientific RuleBased/SelfEvolve
    # treatment. The paired-conformance aliases intentionally remain non-claim.
    rule_evolution = build_nonclaim_evolution_factory()
    self_evolution = build_nonclaim_evolution_factory()
    rule_candidate_materializer = SemPaperCandidateMethodMaterializer(
        method_system=method_system.ports,
        evolution_factory=rule_evolution,
        evolution_provider_id="sem.evolution.rule-based.v1",
        transformer=transformer,
        state_factory=state_factory,
    )
    self_candidate_materializer = SemPaperCandidateMethodMaterializer(
        method_system=method_system.ports,
        evolution_factory=self_evolution,
        evolution_provider_id="sem.evolution.pipeline.evidence-bound.v1",
        transformer=transformer,
        state_factory=state_factory,
    )
    fixed_snapshot_factory = build_sem_paper_live_deluxe_snapshot_factory(
        transformer,
        preset="seed_c_v018",
        candidate_id="sem-paper:closed-world:seed-c:v018",
    )
    fixed_seed_x_snapshot_factory = build_sem_paper_live_deluxe_snapshot_factory(
        transformer,
        preset="seed_x_v018",
        candidate_id="sem-paper:closed-world:seed-x:v018",
    )
    composition = compose_sem_paper(
        SemPaperCompositionPorts(
            method_system=method_system,
            logging=logging,
            planner=meta.capability_composition,
            scope=project_scope,
            evolution_factory=self_evolution,
            evolution_provider_id="sem.evolution.pipeline.evidence-bound.v1",
            serving_factory=build_deluxe_session_serving,
            serving_provider_id="sem.serving.deluxe.grounded.v1",
            self_evolving_serving_factory=build_hybrid_session_serving,
            fixed_deluxe_snapshot_factory=fixed_snapshot_factory,
            fixed_seed_x_deluxe_snapshot_factory=fixed_seed_x_snapshot_factory,
            state_factory=state_factory,
            candidate_method_materializer=self_candidate_materializer,
            rule_based_candidate_method_materializer=rule_candidate_materializer,
            self_evolving_candidate_method_materializer=self_candidate_materializer,
        )
    )
    return composition


def run(inputs: NonMinecraftExperimentInputs) -> int:
    concurrency_runtime = build_execution_concurrency_runtime()
    artifact_group = concurrency_runtime.open_task_group(f"run-artifacts:{inputs.run_id}", tenant_id=inputs.run_id, resource_id="artifacts")
    artifacts = build_directory_run_artifact_store(inputs.output_dir, task_group=artifact_group)
    diagnostics = JsonlRunDiagnostics(artifacts, run_id=inputs.run_id)
    result: dict[str, object] = {
        "run_id": inputs.run_id,
        "status": "starting",
        "scientific_claim": False,
    }
    try:
        if inputs.matrix_profile != "paired-conformance":
            raise NonMinecraftExperimentConfigurationError(
                "non-Minecraft reference execution is portability-only; scientific Core-6 "
                "requires the Minecraft production root and qualified scientific authorities"
            )
        tasks = load_tasks(inputs.tasks_path, inputs.task_ids)
        candidate = build_seed_x_candidate()
        dynamics = ReferenceClosedWorldDynamics()
        environment_factory = _ReferenceEnvironmentFactory(
            compose_state_machine_environment(
                reference_closed_world_spec(),
                dynamics=dynamics,
            )
        )
        protocol = build_sem_paper_study_protocol(
            study_id="sem-paper-non-minecraft-portability",
            workload_id=f"sem-paper:closed-world:{inputs.run_id}",
            task_manifest_digest=canonical_digest(tasks),
            seed_identity={"world": "reference-v1", "repetitions": inputs.repetitions},
            fixed_configuration={"architecture": "seed_c_v018"},
            candidate_configuration={
                "architecture": "seed_x_v018",
                "candidate_id": candidate.candidate_id,
            },
            repetitions=inputs.repetitions,
            matrix_profile=inputs.matrix_profile,
        )
        experiment_plan = compile_sem_paper_experiment_plan(protocol)
        run_spec = ExperimentRunSpec(
            run_id=inputs.run_id,
            project_id="sem-paper-1",
            experiment_id="sem-paper-non-minecraft-portability",
            study_id=protocol.study_id,
            execution_profile="portability-conformance",
            task_manifest_digest=protocol.task_manifest_digest,
            seed_schedule_digest=protocol.seed_schedule_digest,
            repetitions=protocol.repetitions,
            artifact_root=str(inputs.output_dir),
            environment_identity_digest=environment_factory.environment_digest,
        )
        artifacts.publish_json(
            "run_manifest.json",
            {
                "inputs": {
                    **asdict(inputs),
                    "output_dir": str(inputs.output_dir),
                    "tasks_path": str(inputs.tasks_path),
                },
                "run_spec": asdict(run_spec),
                "study_protocol": asdict(protocol),
                "experiment_plan": asdict(experiment_plan),
                "tasks": [asdict(task) for task in tasks],
                "candidate_id": candidate.candidate_id,
                "candidate_target_spec_digest": candidate.target_spec_digest,
                "claim_scope": "portability_conformance_only",
            },
            kind=RunArtifactKind.MANIFEST,
        )
        logging_group = concurrency_runtime.open_task_group(f"logging:{inputs.run_id}", tenant_id=inputs.run_id, resource_id="logging")
        composition = _compose_project(artifacts, task_group=logging_group)
        root = compose_sem_paper_non_minecraft_production_root(
            composition=composition,
            run_spec=run_spec,
            experiment_plan=experiment_plan,
            ports=SemPaperNonMinecraftWorkloadPorts(
                environment_factory=environment_factory,
                planner_factory=ReferenceClosedWorldPlannerFactory(),
                state=ReferenceClosedWorldState(),
                completion=ReferenceClosedWorldCompletion(),
                evidence_factory=SEMClosedWorldEvidenceFactory(),
                observation_sink_factory=_ObservationSinkFactory(artifacts),
                diagnostics=diagnostics,
            ),
            tasks=tasks,
            study_protocol=protocol,
            context=ExecutionContext(
                inputs.run_id,
                f"trace:{inputs.run_id}",
                f"span:{inputs.run_id}",
                study_id=protocol.study_id,
            ),
            run_executor=build_default_experiment_run_application(artifacts),
            candidate=candidate,
            candidate_factory=(
                lambda binding: (
                    candidate
                    if inputs.matrix_profile == "paired-conformance"
                    else build_seed_candidate(binding.seed_id)
                )
            ),
        )
        report = root.execute_run().study_report
        result.update(
            {
                "status": "completed",
                "scientific_claim": False,
                "scientific_claim_reasons": [
                    "deterministic_planner_does_not_use_recalled_memory",
                    "static_seed_x_candidate_not_live_self_evolution",
                    "reference_world_is_a_portability_conformance_domain",
                ],
                "observation_count": len(report.observations),
                "aggregate_count": len(report.aggregates),
                "protocol_digest": protocol.protocol_digest,
            }
        )
        artifacts.publish_json("result.json", result, kind=RunArtifactKind.RESULT)
        return 0
    except BaseException as exc:
        descriptor = describe_exception(exc)
        result.update(
            {
                "status": "failed",
                "error_type": descriptor.error_type,
                "error": descriptor.safe_message,
                "error_digest": descriptor.error_digest,
                "cause_chain": exception_chain(exc),
            }
        )
        artifacts.publish_json("result.json", result, kind=RunArtifactKind.RESULT)
        raise
    finally:
        concurrency_runtime.close()


__all__ = [
    "NonMinecraftExperimentConfigurationError",
    "NonMinecraftExperimentInputs",
    "load_tasks",
    "parse_inputs",
    "run",
]
