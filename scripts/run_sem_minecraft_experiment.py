"""Run the current SEM Minecraft production graph.

This is the experiment entrypoint for the current repository.  It composes the
project and platform seams explicitly, starts one source Minecraft service,
and executes the complete frozen study matrix through per-repetition verified
world cuts.
The ``baseline`` mode is deliberately model-backed; ``scripted-smoke`` is
plumbing-only and must never be reported as a scientific result.

Secrets are read from environment variables and are never accepted as CLI
arguments or written to the run manifest.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import traceback
from typing import Mapping
from uuid import uuid4

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from projects.sem_paper.composition import (
    MinecraftTaskSpec,
    ScriptedMinecraftPlanner,
    SemPaperCompositionPorts,
    SemPaperCandidateMethodMaterializer,
    SemPaperMinecraftBranchRequestFactory,
    SemPaperMinecraftHostInputs,
    SemPaperModelPlanner,
    SemPaperModelPlannerBinding,
    SemPaperModelPlannerFactory,
    compose_sem_paper,
    compose_sem_paper_minecraft_production_root,
    build_seed_x_candidate,
    build_sem_paper_study_protocol,
    task_from_mapping,
    validate_task_manifest,
)
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from projects.sem_paper.method.self_evolving_memory.session_evolution_api import SessionEvolutionFactory
from projects.sem_paper.method.self_evolving_memory.minecraft_transform import (
    MinecraftGroundedSemanticTransformer,
)
from projects.sem_paper.method.self_evolving_memory.serving_providers import (
    build_deluxe_session_serving,
    build_hybrid_session_serving,
)
from projects.sem_paper.method.self_evolving_memory.typed_materialization import (
    build_sem_paper_live_deluxe_snapshot_factory,
)
from research_platform.environment.minecraft.api import (
    MinecraftAgentSpec,
    MinecraftBridgeSpec,
    MinecraftEndpointSpec,
    MinecraftEnvironmentSpec,
    MinecraftRconEndpoint,
    MinecraftServerSpec,
)
from research_platform.environment.minecraft.composition import (
    LocalMinecraftExperimentHostFactory,
    MinecraftExperimentHostInputs,
    MinecraftServerServiceFactory,
    MinecraftServerServiceFactoryConfig,
    compose_minecraft_environment,
)
from research_platform.environment.minecraft.providers.rcon import MinecraftRconConsole
from research_platform.environment.minecraft.providers.readiness import minecraft_preflight, report_json
from research_platform.environment.minecraft.providers.world_cut import (
    FilesystemMinecraftWorldCopier,
    ReflinkMinecraftWorldCopier,
)
from research_platform.experimentation.run.api import ExperimentRunSpec, RunArtifactKind, RunDiagnosticsPort
from research_platform.experimentation.run.runtime import (
    DirectoryRunArtifactStore,
    JsonlRunDiagnostics,
    exception_chain,
    json_default,
)
from research_platform.experimentation.study.api import StudyMatrixExecutionReport, StudyProtocol, VariantKind
from research_platform.experimentation.run.composition import build_default_experiment_run_application
from research_platform.model.request.prompt.composition import FrozenPromptRequestBinding
from research_platform.model.request.prompt.runtime import (
    PromptRegistry,
    default_block_policies,
    default_output_schemas,
    default_prompt_specs,
)
from research_platform.model.request.composition import build_directory_model_request_recorder
from research_platform.model.serving.endpoint.api import QualifiedModelEndpointBinding
from research_platform.model.serving.endpoint.composition import (
    PersistedQualifiedModelEndpointBinding,
    build_openai_compatible_qualified_endpoint,
    load_qualified_model_deployment_closure,
)
from research_platform.model.serving.providers.runtime_qualification_storage import (
    DirectoryRuntimeQualificationEvidenceStore,
)
from research_platform.observability.logging.composition import (
    LogQueryBinding,
    LogSinkBinding,
    compose_logging_system,
)
from research_platform.observability.logging.storage.runtime import InMemoryLogStore
from research_platform.participant.method.composition import compose_default_method_system
from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.platform.kernel import ExecutionContext, canonical_digest
from research_platform.runtime.host.composition import compose_local_host
from research_platform.runtime.host.providers import LocalOperatingSystemRoute
from research_platform.runtime.service.runtime.environment import MaterializedServiceEnvironment
from research_platform.resource.resolution.api import ResourceResolutionRequest
from research_platform.resource.resolution.composition import build_local_resource_resolver
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind


class ExperimentConfigurationError(ValueError):
    """The live experiment inputs are incomplete or inconsistent."""


_PLANNER_PROMPT_GENERATION = "sem-paper-planner-generation-v1"


class RunArtifactMethodObservationSink:
    def __init__(self, artifacts: DirectoryRunArtifactStore, name: str) -> None:
        self._artifacts = artifacts
        self._name = name

    def record(self, observation: object) -> None:
        self._artifacts.append_json(
            self._name,
            {"observation": observation},
            kind=RunArtifactKind.EVIDENCE,
        )


class _BranchEnvironmentFactory:
    def __init__(self, *, operating_system: LocalOperatingSystemRoute, diagnostics: RunDiagnosticsPort) -> None:
        self._operating_system = operating_system
        self._diagnostics = diagnostics

    def compose(self, spec: MinecraftEnvironmentSpec):
        return compose_minecraft_environment(
            spec,
            operating_system=self._operating_system,
            diagnostics=self._diagnostics,
        )


@dataclass(frozen=True, slots=True)
class ExperimentInputs:
    mode: str
    run_id: str
    output_dir: Path
    server_jar: Path
    server_libraries_dir: Path | None
    bridge_dir: Path
    source_workdir: Path
    snapshot_root: Path
    branch_root: Path
    server_host: str
    source_port: int
    branch_ports: tuple[int, ...]
    source_rcon_port: int
    minecraft_version: str
    minecraft_username: str
    server_seed: str
    node_executable: str
    java_executable: str
    model_base_url: str
    model_id: str
    model_family: str
    model_timeout_s: float
    model_context_length: int
    tasks_path: Path
    task_ids: tuple[str, ...]
    accept_eula: bool
    rcon_password_env: str
    generate_ephemeral_rcon_secret: bool
    qualified_model_closure: Path | None


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or not value.strip():
        raise ExperimentConfigurationError(f"required environment variable is missing: {name}")
    return value.strip()


def _ports(value: str) -> tuple[int, ...]:
    result = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not result or any(not 1 <= port <= 65535 for port in result):
        raise ExperimentConfigurationError("Minecraft port list is invalid")
    if len(result) != len(set(result)):
        raise ExperimentConfigurationError("Minecraft port list contains duplicates")
    return result


def parse_inputs(argv: list[str] | None = None) -> ExperimentInputs:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "scripted-smoke", "baseline"), default="baseline")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--server-jar", type=Path, default=None)
    parser.add_argument("--server-libraries-dir", type=Path, default=None)
    parser.add_argument("--bridge-dir", type=Path, default=None)
    parser.add_argument("--source-workdir", type=Path, default=None)
    parser.add_argument("--snapshot-root", type=Path, default=None)
    parser.add_argument("--branch-root", type=Path, default=None)
    parser.add_argument("--server-host", default=os.environ.get("SEM_MC_SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--source-port", type=int, default=int(os.environ.get("SEM_MC_SOURCE_PORT", "25565")))
    parser.add_argument("--branch-ports", default=os.environ.get("SEM_MC_BRANCH_PORTS", "25566,25567"))
    parser.add_argument("--source-rcon-port", type=int, default=int(os.environ.get("SEM_MC_SOURCE_RCON_PORT", "25575")))
    parser.add_argument("--minecraft-version", default=os.environ.get("SEM_MC_VERSION", "1.21.8"))
    parser.add_argument("--minecraft-username", default=os.environ.get("SEM_MC_USERNAME", "ResearchBot"))
    parser.add_argument("--server-seed", default=os.environ.get("SEM_MC_SEED", "SEM_PAPER_FIXED_WORLD_V1"))
    parser.add_argument("--node-executable", default=os.environ.get("SEM_MC_NODE", ""))
    parser.add_argument("--java-executable", default=os.environ.get("SEM_MC_JAVA", ""))
    parser.add_argument("--model-base-url", default=os.environ.get("SEM_MC_MODEL_BASE_URL", ""))
    parser.add_argument("--model-id", default=os.environ.get("SEM_MC_MODEL_ID", ""))
    parser.add_argument("--model-family", default=os.environ.get("SEM_MC_MODEL_FAMILY", "qwen3.6"))
    parser.add_argument("--model-timeout-s", type=float, default=float(os.environ.get("SEM_MC_MODEL_TIMEOUT_S", "120")))
    parser.add_argument("--model-context-length", type=int, default=int(os.environ.get("SEM_MC_MODEL_CONTEXT_LENGTH", "262144")))
    parser.add_argument(
        "--qualified-model-closure",
        type=Path,
        default=None,
        help="path to the platform-published qualified model deployment closure",
    )
    parser.add_argument("--tasks", type=Path, default=None)
    parser.add_argument("--task-ids", default=os.environ.get("SEM_MC_TASK_IDS", ""))
    parser.add_argument("--accept-minecraft-eula", action="store_true")
    parser.add_argument("--rcon-password-env", default=os.environ.get("SEM_MC_RCON_PASSWORD_ENV", "SEM_MC_RCON_PASSWORD"))
    parser.add_argument(
        "--generate-ephemeral-rcon-secret",
        action="store_true",
        help=(
            "explicitly generate a process-scoped random RCON secret when the "
            "declared environment variable is absent; never persist its value"
        ),
    )
    args = parser.parse_args(argv)

    repo_root = _REPOSITORY_ROOT
    run_id = args.run_id.strip() or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output_raw = str(args.output_dir or repo_root / "runs" / "sem_paper" / run_id)
    server_jar_raw = str(args.server_jar or os.environ.get("SEM_MC_SERVER_JAR", "")).strip()
    if not server_jar_raw:
        raise ExperimentConfigurationError("SEM_MC_SERVER_JAR or --server-jar is required")
    libraries_value = args.server_libraries_dir or os.environ.get("SEM_MC_SERVER_LIBRARIES_DIR", "")
    qualified_closure_value = args.qualified_model_closure or os.environ.get(
        "SEM_MC_QUALIFIED_MODEL_CLOSURE",
        "",
    )
    try:
        resource_resolver = build_local_resource_resolver()
        output_binding = resource_resolver.resolve(
            ResourceResolutionRequest(
                "sem-paper-run-paths",
                str(repo_root),
                paths=(("output", output_raw),),
            )
        )
        output = Path(output_binding.path("output"))
        path_rows = [
            ("server_jar", server_jar_raw),
            ("bridge_dir", str(args.bridge_dir or os.environ.get(
                "SEM_MC_BRIDGE_DIR",
                repo_root / "research_platform" / "environment" / "minecraft" / "providers" / "assets" / "mineflayer_bridge",
            ))),
            ("source_workdir", str(args.source_workdir or os.environ.get("SEM_MC_SOURCE_WORKDIR", output / "source-server"))),
            ("snapshot_root", str(args.snapshot_root or os.environ.get("SEM_MC_SNAPSHOT_ROOT", output / "world-cuts"))),
            ("branch_root", str(args.branch_root or os.environ.get("SEM_MC_BRANCH_ROOT", output / "branches"))),
            ("tasks", str(args.tasks or os.environ.get(
                "SEM_MC_TASKS",
                repo_root / "projects" / "sem_paper" / "experiments" / "manifests" / "dev_neutral.json",
            ))),
        ]
        if str(libraries_value).strip():
            path_rows.append(("server_libraries", str(libraries_value)))
        if str(qualified_closure_value).strip():
            path_rows.append(("qualified_model_closure", str(qualified_closure_value)))
        path_binding = resource_resolver.resolve(
            ResourceResolutionRequest("sem-paper-run-resources", str(repo_root), paths=tuple(path_rows))
        )
        executable_rows = (
            ("node", args.node_executable.strip() or "node"),
            ("java", args.java_executable.strip() or "java"),
        )
        executable_binding = resource_resolver.resolve(
            ResourceResolutionRequest("sem-paper-run-executables", str(repo_root), executables=executable_rows)
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise ExperimentConfigurationError(f"resource resolution failed: {exc}") from exc
    server_jar = Path(path_binding.path("server_jar"))
    server_libraries_dir = Path(path_binding.path("server_libraries")) if str(libraries_value).strip() else None
    bridge_dir = Path(path_binding.path("bridge_dir"))
    source_workdir = Path(path_binding.path("source_workdir"))
    snapshot_root = Path(path_binding.path("snapshot_root"))
    branch_root = Path(path_binding.path("branch_root"))
    tasks_path = Path(path_binding.path("tasks"))
    node = executable_binding.executable("node")
    java = executable_binding.executable("java")
    model_base_url = args.model_base_url.strip()
    model_id = args.model_id.strip()
    if not 1 <= args.source_port <= 65535 or not 1 <= args.source_rcon_port <= 65535:
        raise ExperimentConfigurationError("Minecraft source ports must be between 1 and 65535")
    if args.model_timeout_s <= 0 or args.model_context_length <= 0:
        raise ExperimentConfigurationError("model timeout and context length must be positive")
    if server_libraries_dir is not None and not server_libraries_dir.is_dir():
        raise ExperimentConfigurationError(
            f"Minecraft server libraries directory is missing: {server_libraries_dir}"
        )
    if args.source_port in _ports(args.branch_ports):
        raise ExperimentConfigurationError("source server port overlaps branch port candidates")
    if args.source_rcon_port in (args.source_port, *_ports(args.branch_ports)):
        raise ExperimentConfigurationError("source RCON port overlaps a server port")
    task_ids = tuple(item.strip() for item in args.task_ids.split(",") if item.strip())
    return ExperimentInputs(
        mode=args.mode,
        run_id=run_id,
        output_dir=output,
        server_jar=server_jar,
        server_libraries_dir=server_libraries_dir,
        bridge_dir=bridge_dir,
        source_workdir=source_workdir,
        snapshot_root=snapshot_root,
        branch_root=branch_root,
        server_host=args.server_host,
        source_port=args.source_port,
        branch_ports=_ports(args.branch_ports),
        source_rcon_port=args.source_rcon_port,
        minecraft_version=args.minecraft_version,
        minecraft_username=args.minecraft_username,
        server_seed=args.server_seed,
        node_executable=node,
        java_executable=java,
        model_base_url=model_base_url,
        model_id=model_id,
        model_family=args.model_family,
        model_timeout_s=args.model_timeout_s,
        model_context_length=args.model_context_length,
        tasks_path=tasks_path,
        task_ids=task_ids,
        accept_eula=bool(args.accept_minecraft_eula),
        rcon_password_env=args.rcon_password_env,
        generate_ephemeral_rcon_secret=bool(args.generate_ephemeral_rcon_secret),
        qualified_model_closure=(
            Path(path_binding.path("qualified_model_closure"))
            if str(qualified_closure_value).strip()
            else None
        ),
    )


def load_tasks(path: Path, selected: tuple[str, ...]) -> tuple[MinecraftTaskSpec, ...]:
    if not path.is_file():
        raise ExperimentConfigurationError(f"task manifest is missing: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExperimentConfigurationError(f"task manifest is not valid JSON: {path}") from exc
    if not isinstance(raw, Mapping) or not isinstance(raw.get("tasks"), list):
        raise ExperimentConfigurationError("task manifest must contain a list at tasks")
    if any(not isinstance(row, Mapping) for row in raw["tasks"]):
        raise ExperimentConfigurationError("task manifest contains a non-mapping task")
    try:
        tasks = tuple(task_from_mapping(row) for row in raw["tasks"])
        tasks = validate_task_manifest(tasks, selected_ids=selected)
    except (KeyError, TypeError, ValueError) as exc:
        raise ExperimentConfigurationError(f"task manifest validation failed: {exc}") from exc
    if not tasks:
        raise ExperimentConfigurationError("task manifest selected no tasks")
    return tasks


def _register_scopes(meta) -> ScopeIdentity:
    workspace = ScopeIdentity(ScopeKind.WORKSPACE, "sem-paper-workspace")
    program = ScopeIdentity(ScopeKind.PROGRAM, "sem-paper-program")
    project = ScopeIdentity(ScopeKind.PROJECT, "sem-paper-1")
    meta.scopes.register(workspace, PLATFORM_SCOPE)
    meta.scopes.register(program, workspace)
    meta.scopes.register(project, program)
    return project


def _service_environment() -> MaterializedServiceEnvironment:
    allowed = ("HOME", "PATH", "LANG", "LC_ALL", "JAVA_HOME", "TMPDIR")
    values = {key: os.environ[key] for key in allowed if os.environ.get(key)}
    return MaterializedServiceEnvironment.from_mapping(values, "sem-paper:service-environment:v1")


def _paired_workload_id(run_id: str, *, role, branch) -> str:
    """Return one workload identity shared by the paired study branches.

    Branch identity is deliberately separate: control and candidate must have
    different branch ids while their task workload, source cut, environment
    generation and task manifest remain comparable.  Encoding role or branch
    into this field makes the evaluator reject an otherwise valid pair.
    """

    del role, branch
    if not run_id.strip():
        raise ValueError("paired workload identity requires a run id")
    return f"sem-paper:paired:{run_id}"


def _build_planner(
    inputs: ExperimentInputs,
    artifacts: DirectoryRunArtifactStore,
    *,
    qualified_binding: QualifiedModelEndpointBinding | None = None,
):
    if inputs.mode == "scripted-smoke":
        class ScriptedFactory:
            def create(self, *, role, candidate, task, method):
                del role, candidate, method
                script = task.script or ({"tool": "finish", "args": {"reason": "scripted_smoke"}},)
                return ScriptedMinecraftPlanner(tuple(script))
        return ScriptedFactory()

    if qualified_binding is None:
        raise ExperimentConfigurationError(
            "baseline requires a platform-qualified model endpoint binding; "
            "operator-declared SEM_MC_MODEL_* identity is not sufficient"
        )

    registry = PromptRegistry()
    registry.publish(_PLANNER_PROMPT_GENERATION, default_prompt_specs(inputs.model_family))
    recorder = build_directory_model_request_recorder(
        Path(artifacts.directory("model", kind=RunArtifactKind.MODEL))
    )
    prompt_binding = FrozenPromptRequestBinding(
        registry=registry,
        prompt_id="planner.v6",
        policy=default_block_policies()["planner"],
        schemas=default_output_schemas(),
        model_requests=recorder,
    )
    if qualified_binding.prompt_generation != prompt_binding.prompt_generation_id:
        raise ExperimentConfigurationError(
            "qualified model binding prompt generation does not match the frozen prompt registry"
        )
    deployment_id = qualified_binding.deployment_id
    deployment_generation = qualified_binding.deployment_generation
    api_key = os.environ.get("SEM_MC_MODEL_API_KEY", "")
    endpoint = build_openai_compatible_qualified_endpoint(
        qualified_binding,
        api_key=api_key,
        timeout_s=None,
    )
    model = qualified_binding.model
    if inputs.model_id and model.model_id != inputs.model_id:
        raise ExperimentConfigurationError(
            "qualified model binding model_id does not match the requested model"
        )
    return SemPaperModelPlannerFactory(
        SemPaperModelPlannerBinding(
            prompt_requests=prompt_binding,
            body_builder=SemPaperModelPlanner.body,
            model=model,
            deployment_id=deployment_id,
            deployment_generation=deployment_generation,
            context_length=inputs.model_context_length,
            endpoint=endpoint,
        )
    )


def build_runtime(
    inputs: ExperimentInputs,
    tasks: tuple[MinecraftTaskSpec, ...],
    study_protocol: StudyProtocol,
    diagnostics: RunDiagnosticsPort,
    artifacts: DirectoryRunArtifactStore,
    candidate,
    evolution_factory: SessionEvolutionFactory,
    qualified_binding: QualifiedModelEndpointBinding | None = None,
):
    if inputs.mode == "baseline" and qualified_binding is None:
        raise ExperimentConfigurationError(
            "model-backed SEM production composition requires a persisted qualified model binding; "
            "operator model metadata cannot establish scientific identity"
        )
    meta = build_in_memory_platform_meta()
    project_scope = _register_scopes(meta)
    log_store = InMemoryLogStore()
    logging = compose_logging_system(
        sink=LogSinkBinding(log_store, "sem-paper.in-memory-log-store.v1", canonical_digest({"kind": "in-memory"})),
        query=LogQueryBinding(log_store, "sem-paper.in-memory-log-store.v1", canonical_digest({"kind": "in-memory"})),
        planner=meta.capability_composition,
        scope=project_scope,
    )
    method_system = compose_default_method_system(planner=meta.capability_composition, scope=project_scope)
    candidate_method_materializer = SemPaperCandidateMethodMaterializer(
        method_system=method_system.ports,
        evolution_factory=evolution_factory,
        evolution_provider_id="sem.evolution.pipeline.bound.v1",
        transformer=MinecraftGroundedSemanticTransformer(),
    )
    fixed_deluxe_snapshot_factory = build_sem_paper_live_deluxe_snapshot_factory(
        MinecraftGroundedSemanticTransformer(),
        preset="seed_c_v018",
        candidate_id="sem-paper:deluxe:seed-c:v018",
    )
    project = compose_sem_paper(
        SemPaperCompositionPorts(
            method_system=method_system,
            logging=logging,
            planner=meta.capability_composition,
            scope=project_scope,
            evolution_factory=evolution_factory,
            evolution_provider_id="sem.evolution.pipeline.bound.v1",
            serving_factory=build_deluxe_session_serving,
            serving_provider_id="sem.serving.deluxe.seed-c.v018",
            self_evolving_serving_factory=build_hybrid_session_serving,
            fixed_deluxe_snapshot_factory=fixed_deluxe_snapshot_factory,
            candidate_method_materializer=candidate_method_materializer,
        )
    )
    host = compose_local_host(planner=meta.capability_composition)
    os_route = host.operating_system
    service_environment = _service_environment()
    server_config = MinecraftServerServiceFactoryConfig(
        environment=service_environment,
        state_root=Path(artifacts.directory("service-state", kind=RunArtifactKind.LOG)),
        intent_root=Path(artifacts.directory("service-intents", kind=RunArtifactKind.LOG)),
        capture_root=Path(artifacts.directory("service-captures", kind=RunArtifactKind.LOG)),
        operating_system=os_route,
        accept_eula=inputs.accept_eula,
    )
    branch_server_factory = MinecraftServerServiceFactory(server_config)
    source_rcon = MinecraftRconEndpoint(host=inputs.server_host, port=inputs.source_rcon_port)
    source_spec = MinecraftServerSpec(
        jar_path=str(inputs.server_jar),
        workdir=str(inputs.source_workdir),
        java_executable=inputs.java_executable,
        libraries_dir=(str(inputs.server_libraries_dir) if inputs.server_libraries_dir is not None else None),
        host=inputs.server_host,
        port=inputs.source_port,
        level_name="sem-paper-source-world",
        level_seed=inputs.server_seed,
        rcon_endpoint=source_rcon,
    )
    password = os.environ.get(inputs.rcon_password_env, "")
    if not password:
        if not inputs.generate_ephemeral_rcon_secret:
            raise ExperimentConfigurationError(
                f"RCON secret is missing in environment variable {inputs.rcon_password_env}"
            )
        password = secrets.token_urlsafe(32)
        diagnostics.event(
            phase="composition",
            event="RCON_EPHEMERAL_SECRET_GENERATED",
            level="INFO",
            attributes={
                "provider": "process-ephemeral",
                "persisted": False,
                "environment_variable": inputs.rcon_password_env,
            },
            correlation_refs=(inputs.run_id,),
        )
    source_config = MinecraftServerServiceFactoryConfig(
        environment=service_environment,
        state_root=Path(artifacts.directory("source-service-state", kind=RunArtifactKind.LOG)),
        intent_root=Path(artifacts.directory("source-service-intents", kind=RunArtifactKind.LOG)),
        capture_root=Path(artifacts.directory("source-service-captures", kind=RunArtifactKind.LOG)),
        operating_system=os_route,
        accept_eula=inputs.accept_eula,
        rcon_password_provider=lambda: password,
    )
    source_server_factory = MinecraftServerServiceFactory(source_config)
    console = MinecraftRconConsole(source_rcon, secret_provider=lambda: password)
    bridge_path = inputs.bridge_dir / "bridge.js"
    bridge_stderr = Path(artifacts.path("bridge.stderr.log", kind=RunArtifactKind.LOG))
    environment_template = MinecraftEnvironmentSpec(
        endpoint=MinecraftEndpointSpec(inputs.server_host, inputs.source_port),
        bridge=MinecraftBridgeSpec((inputs.node_executable, str(bridge_path)), str(inputs.bridge_dir), stderr_log_path=str(bridge_stderr)),
        agent=MinecraftAgentSpec(username=inputs.minecraft_username, version=inputs.minecraft_version),
    )
    branch_template = MinecraftServerSpec(
        jar_path=str(inputs.server_jar),
        workdir=str(inputs.source_workdir),
        java_executable=inputs.java_executable,
        libraries_dir=(str(inputs.server_libraries_dir) if inputs.server_libraries_dir is not None else None),
        host=inputs.server_host,
        port=inputs.source_port,
        level_name="sem-paper-branch-placeholder",
        level_seed=inputs.server_seed,
    )
    host_inputs = SemPaperMinecraftHostInputs(
        environment_template=environment_template,
        server_template=branch_template,
        server_candidate_ports=inputs.branch_ports,
    )
    request_factory = SemPaperMinecraftBranchRequestFactory(host_inputs)

    def report_copy_fallback(detail: str) -> None:
        diagnostics.event(
            phase="world_cut",
            event="WORLD_COPY_COPIER_FALLBACK",
            level="WARN",
            attributes={
                "policy": "reflink_then_explicit_filesystem",
                "reason": detail,
            },
            correlation_refs=(inputs.run_id,),
        )

    world_copier = (
        ReflinkMinecraftWorldCopier(
            fallback_copier=FilesystemMinecraftWorldCopier(),
            fallback_reporter=report_copy_fallback,
        )
        if os_route.is_posix
        else FilesystemMinecraftWorldCopier()
    )
    minecraft_host = LocalMinecraftExperimentHostFactory(
        MinecraftExperimentHostInputs(
            source_server_spec=source_spec,
            source_console=console,
            source_server_factory=source_server_factory,
            branch_server_factory=branch_server_factory,
            endpoint_allocations=meta.endpoint_allocations,
            environment_factory=_BranchEnvironmentFactory(operating_system=os_route, diagnostics=diagnostics),
            snapshot_root=inputs.snapshot_root,
            branch_root=inputs.branch_root,
            source_environment_generation=canonical_digest(
                {"source": source_spec.level_name, "jar": str(inputs.server_jar)}
            ),
            copier=world_copier,
        )
    )
    host = minecraft_host.open()
    context = ExecutionContext(
        inputs.run_id,
        f"trace:{inputs.run_id}",
        f"span:{inputs.run_id}",
        study_id="sem-paper-minecraft",
        condition_id="fixed-memory-control",
    )
    planner_factory = _build_planner(inputs, artifacts, qualified_binding=qualified_binding)
    class ObservationSinkFactory:
        def create(self, *, role, branch):
            del role
            return RunArtifactMethodObservationSink(
                artifacts,
                f"method_observations/{branch.branch_id.replace(':', '_')}.jsonl",
            )

    run_executor = build_default_experiment_run_application(artifacts)
    root = compose_sem_paper_minecraft_production_root(
        composition=project,
        run_spec=run_spec,
        world_cuts=host.world_cuts,
        branch_runtime_factory=host.branch_runtime_factory,
        request_factory=request_factory,
        planner_factory=planner_factory,
        observation_sink_factory=ObservationSinkFactory(),
        tasks=tasks,
        context=context,
        workload_id_factory=lambda role, branch: _paired_workload_id(
            inputs.run_id,
            role=role,
            branch=branch,
        ),
        session_id=f"{inputs.run_id}:source-cut",
        branch_id_factory=lambda role, repetition: f"{inputs.run_id}:{role.value}:rep-{repetition}",
        destination_factory=lambda branch_id: str(inputs.branch_root / branch_id.replace(":", "_")),
        diagnostics=diagnostics,
        artifact_store=artifacts,
        study_protocol=study_protocol,
        run_executor=run_executor,
        candidate=candidate,
    )
    return root, host, log_store


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_digest(root: Path, *, suffixes: tuple[str, ...]) -> str | None:
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    paths = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in suffixes)
    for path in paths:
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _write_manifest(
    inputs: ExperimentInputs,
    tasks: tuple[MinecraftTaskSpec, ...],
    candidate,
    study_protocol: StudyProtocol,
    artifacts: DirectoryRunArtifactStore,
    qualified_binding: QualifiedModelEndpointBinding | None = None,
    run_spec: ExperimentRunSpec | None = None,
) -> None:
    safe = asdict(inputs)
    safe.pop("output_dir", None)
    safe["server_jar"] = str(inputs.server_jar)
    safe["server_libraries_dir"] = (
        str(inputs.server_libraries_dir) if inputs.server_libraries_dir is not None else None
    )
    safe["bridge_dir"] = str(inputs.bridge_dir)
    safe["source_workdir"] = str(inputs.source_workdir)
    safe["snapshot_root"] = str(inputs.snapshot_root)
    safe["branch_root"] = str(inputs.branch_root)
    safe["tasks_path"] = str(inputs.tasks_path)
    safe["qualified_model_closure"] = (
        str(inputs.qualified_model_closure)
        if inputs.qualified_model_closure is not None
        else None
    )
    safe["rcon_password_env"] = inputs.rcon_password_env
    safe["generate_ephemeral_rcon_secret"] = inputs.generate_ephemeral_rcon_secret
    safe["tasks"] = [asdict(task) for task in tasks]
    safe["study_protocol"] = asdict(study_protocol)
    safe["run_spec"] = asdict(run_spec) if run_spec is not None else None
    safe["run_spec_digest"] = run_spec.identity_digest() if run_spec is not None else None
    safe["task_manifest"] = {
        "path": str(inputs.tasks_path),
        "sha256": _sha256_file(inputs.tasks_path),
        "manifest_id": json.loads(inputs.tasks_path.read_text(encoding="utf-8")).get("manifest_id")
        if inputs.tasks_path.is_file()
        else None,
        "selected_task_ids": [task.task_id for task in tasks],
        "resolved_task_order": [task.task_id for task in tasks],
        "resolved_digest": canonical_digest(tasks),
    }
    safe["candidate"] = {
        "base_generation": candidate.base_generation,
        "candidate_id": candidate.candidate_id,
        "target_spec_digest": candidate.target_spec_digest,
        "primitive_edits": [
            {"kind": edit.kind.value, "target": edit.target}
            for edit in candidate.primitive_edits
        ],
    }
    safe["server_jar_sha256"] = hashlib.sha256(inputs.server_jar.read_bytes()).hexdigest() if inputs.server_jar.is_file() else None
    safe["runtime_identity"] = {
        "python": sys.version,
        "platform": sys.platform,
        "source_code_digest": canonical_digest(
            {
                "paper": _tree_digest(_REPOSITORY_ROOT / "projects" / "sem_paper", suffixes=(".py", ".json", ".md")),
                "minecraft_environment": _tree_digest(_REPOSITORY_ROOT / "research_platform" / "environment" / "minecraft", suffixes=(".py", ".js", ".json")),
                "entrypoint": _sha256_file(Path(__file__).resolve()),
            }
        ),
        "bridge_js_sha256": _sha256_file(inputs.bridge_dir / "bridge.js"),
        "bridge_lock_sha256": _sha256_file(inputs.bridge_dir / "package-lock.json"),
        "server_libraries_digest": _tree_digest(inputs.server_libraries_dir, suffixes=(".jar",)) if inputs.server_libraries_dir else None,
    }
    safe["model_identity"] = (
        {
            "status": "qualified",
            "role": qualified_binding.role,
            "deployment_id": qualified_binding.deployment_id,
            "deployment_generation": qualified_binding.deployment_generation,
            "model": asdict(qualified_binding.model),
            "model_stack_digest": qualified_binding.model_stack_digest,
            "qualification_certificate_digest": qualified_binding.qualification_certificate_digest,
            "runtime_qualification_digest": qualified_binding.runtime_qualification_digest,
            "host_identity_digest": qualified_binding.host_identity_digest,
            "prompt_generation": qualified_binding.prompt_generation,
        }
        if qualified_binding is not None
        else {
            "status": "unbound",
            "requested_model_id": inputs.model_id or None,
            "requested_model_family": inputs.model_family or None,
            "qualification_required": bool(inputs.model_id),
        }
    )
    artifacts.publish_json("run_manifest.json", safe, kind=RunArtifactKind.MANIFEST)


def _model_request_count(artifacts: DirectoryRunArtifactStore) -> int:
    request_root = Path(artifacts.directory("model/requests", kind=RunArtifactKind.MODEL))
    if not request_root.is_dir():
        return 0
    return sum(1 for path in request_root.glob("*.json") if path.is_file())


def _matrix_metric(
    report: StudyMatrixExecutionReport,
    variant_id: str,
    metric_name: str,
) -> float:
    matches = [
        aggregate.mean
        for aggregate in report.aggregates
        if aggregate.variant_id == variant_id and aggregate.metric_name == metric_name
    ]
    if len(matches) != 1:
        raise ExperimentConfigurationError(
            f"study matrix must contain one aggregate for {variant_id}:{metric_name}"
        )
    return float(matches[0])


def _scientific_claim_gate(
    inputs: ExperimentInputs,
    report: StudyMatrixExecutionReport,
    protocol: StudyProtocol,
    request_count: int,
) -> tuple[bool, dict[str, object]]:
    variant_for_kind = {
        variant.kind: variant.variant_id
        for variant in protocol.variants
    }
    control_id = variant_for_kind.get(VariantKind.CONTROL)
    treatment_id = variant_for_kind.get(VariantKind.TREATMENT)
    if control_id is None or treatment_id is None:
        raise ExperimentConfigurationError("study protocol has no control/treatment variant")
    control_queries = _matrix_metric(report, control_id, "memory_queries_total")
    candidate_queries = _matrix_metric(report, treatment_id, "memory_queries_total")
    control_blocked = _matrix_metric(report, control_id, "task_blocked_total")
    candidate_blocked = _matrix_metric(report, treatment_id, "task_blocked_total")
    reasons: list[str] = []
    if inputs.mode != "baseline":
        reasons.append("mode_is_not_model_backed_baseline")
    # The MC StudyUnit adapter refuses to emit observations unless its paired
    # world-cut comparability proof is valid.  A failed proof therefore aborts
    # the matrix before this gate rather than becoming a false result row.
    if request_count <= 0:
        reasons.append("no_model_request_evidence")
    if control_queries <= 0:
        reasons.append("control_has_no_decision_cycle")
    if candidate_queries <= 0:
        reasons.append("candidate_has_no_decision_cycle")
    if inputs.mode == "baseline":
        reasons.append("live_self_evolving_endpoint_not_used")
        reasons.append("core6_treatment_matrix_not_executed")
        reasons.append("repetition_and_statistical_evidence_not_executed")
    if control_blocked > 0 or candidate_blocked > 0:
        reasons.append("task_dependency_blocking_present")
    gate = {
        "eligible": not reasons,
        "reasons": reasons,
        "comparability_valid": True,
        "model_request_count": request_count,
        "control_memory_queries": control_queries,
        "candidate_memory_queries": candidate_queries,
        "control_blocked_tasks": control_blocked,
        "candidate_blocked_tasks": candidate_blocked,
    }
    return not reasons, gate


def run(inputs: ExperimentInputs) -> int:
    if sys.version_info < (3, 11):
        raise ExperimentConfigurationError("current research-platform requires Python >= 3.11")
    if not inputs.server_jar.is_file():
        raise ExperimentConfigurationError(f"Minecraft server.jar is missing: {inputs.server_jar}")
    if not (inputs.bridge_dir / "bridge.js").is_file():
        raise ExperimentConfigurationError(f"Mineflayer bridge.js is missing: {inputs.bridge_dir}")
    artifacts = DirectoryRunArtifactStore(inputs.output_dir)
    diagnostics = JsonlRunDiagnostics(artifacts, run_id=inputs.run_id)
    host = None
    log_store = None
    started = False
    result: dict[str, object] = {"run_id": inputs.run_id, "mode": inputs.mode, "status": "starting"}
    try:
        tasks = load_tasks(inputs.tasks_path, inputs.task_ids)
        candidate = build_seed_x_candidate()
        qualified_binding: QualifiedModelEndpointBinding | None = None
        if inputs.mode == "baseline":
            if inputs.qualified_model_closure is None:
                raise ExperimentConfigurationError(
                    "baseline requires SEM_MC_QUALIFIED_MODEL_CLOSURE or --qualified-model-closure"
                )
            try:
                closure = load_qualified_model_deployment_closure(
                    inputs.qualified_model_closure,
                    runtime_qualification_store_factory=DirectoryRuntimeQualificationEvidenceStore,
                )
                qualified_binding = PersistedQualifiedModelEndpointBinding(closure).binding_for(
                    role="planner",
                    prompt_generation=_PLANNER_PROMPT_GENERATION,
                )
            except (OSError, TypeError, ValueError) as exc:
                raise ExperimentConfigurationError(
                    f"qualified model deployment closure is invalid: {exc}"
                ) from exc
        study_protocol = build_sem_paper_study_protocol(
            study_id="sem-paper-minecraft",
            workload_id=f"{inputs.run_id}:paired-workload",
            task_manifest_digest=canonical_digest(tuple(task.as_experiment_task() for task in tasks)),
            seed_identity={"server_seed": inputs.server_seed, "repetitions": 1},
            fixed_configuration={"treatment": "fixed_memory", "serving": "seed_c.v018"},
            candidate_configuration={
                "treatment": "candidate",
                "candidate_id": candidate.candidate_id,
                "target_spec_digest": candidate.target_spec_digest,
            },
        )
        run_spec = ExperimentRunSpec(
            run_id=inputs.run_id,
            project_id="sem-paper-1",
            experiment_id="sem-paper-minecraft",
            study_id=study_protocol.study_id,
            execution_profile=inputs.mode,
            task_manifest_digest=study_protocol.task_manifest_digest,
            seed_schedule_digest=study_protocol.seed_schedule_digest,
            repetitions=study_protocol.repetitions,
            artifact_root=str(inputs.output_dir),
            environment_identity_digest=canonical_digest(
                {
                    "kind": "minecraft",
                    "version": inputs.minecraft_version,
                    "server_seed": inputs.server_seed,
                    "server_jar_sha256": _sha256_file(inputs.server_jar),
                }
            ),
            model_binding_digest=(
                canonical_digest(qualified_binding) if qualified_binding is not None else None
            ),
            prompt_generation=(
                qualified_binding.prompt_generation if qualified_binding is not None else None
            ),
        )
        _write_manifest(
            inputs,
            tasks,
            candidate,
            study_protocol,
            artifacts,
            qualified_binding=qualified_binding,
            run_spec=run_spec,
        )
        if inputs.mode == "preflight":
            probes = minecraft_preflight(
                inputs.bridge_dir,
                host=inputs.server_host,
                port=inputs.source_port,
                check_server=False,
                node_command=inputs.node_executable,
                java_command=inputs.java_executable,
            )
            artifacts.publish_json(
                "preflight.json",
                json.loads(report_json(probes)),
                kind=RunArtifactKind.PREFLIGHT,
            )
            if not all(probe.ok for probe in probes):
                failed = ", ".join(f"{probe.name}:{probe.cause_code}" for probe in probes if not probe.ok)
                raise ExperimentConfigurationError(f"Minecraft preflight failed: {failed}")
            result = {"run_id": inputs.run_id, "mode": inputs.mode, "status": "preflight_ok", "task_count": len(tasks)}
            artifacts.publish_json("result.json", result, kind=RunArtifactKind.RESULT)
            return 0
        if not LocalOperatingSystemRoute().is_posix:
            raise ExperimentConfigurationError(
                "live Minecraft launch requires a POSIX host with the exact Linux process provider; "
                "run this entrypoint on the Ubuntu target"
            )
        root, host, log_store = build_runtime(
            inputs,
            tasks,
            study_protocol,
            diagnostics,
            artifacts,
            candidate,
            qualified_binding=qualified_binding,
        )
        host.start_source()
        started = True
        study_report = root.execute_run().study_report
        model_request_count = _model_request_count(artifacts)
        scientific_claim, claim_gate = _scientific_claim_gate(
            inputs,
            study_report,
            root.study_protocol,
            model_request_count,
        )
        result.update(
            {
                "status": "completed",
                "scientific_claim": scientific_claim,
                "scientific_claim_gate": claim_gate,
                "scientific_scope": (
                    "paired_control_vs_static_seed_x_v018_model_backed_not_full_baseline"
                    if inputs.mode == "baseline"
                    else "paired_control_vs_static_seed_x_v018_plumbing_only"
                ),
                "candidate": {
                    "candidate_id": candidate.candidate_id,
                    "target_spec_digest": candidate.target_spec_digest,
                },
                "study_observation_count": len(study_report.observations),
                "study_protocol_digest": root.study_protocol.protocol_digest,
                "study_aggregate_count": len(study_report.aggregates),
            }
        )
        artifacts.publish_json("result.json", result, kind=RunArtifactKind.RESULT)
        return 0
    except BaseException as exc:
        result.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": "".join(traceback.format_exception(exc)),
                "cause_chain": exception_chain(exc),
            }
        )
        artifacts.publish_json("result.json", result, kind=RunArtifactKind.RESULT)
        raise
    finally:
        if started and host is not None:
            try:
                host.stop_source()
            except BaseException as exc:
                cleanup = {
                    "phase": "source_stop",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": "".join(traceback.format_exception(exc)),
                    "cause_chain": exception_chain(exc),
                }
                artifacts.publish_json("cleanup_failure.json", cleanup, kind=RunArtifactKind.CLEANUP)
                diagnostics.failure(
                    phase="cleanup",
                    code="MC_SOURCE_STOP_FAILED",
                    message=str(exc),
                    exception=exc,
                )
        if log_store is not None:
            rows = [row.to_dict() for row in log_store.query(limit=100000)]
            artifacts.publish_json("logs.json", rows, kind=RunArtifactKind.LOG)


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_inputs(argv))
    except Exception as exc:
        print(f"SEM_MINECRAFT_EXPERIMENT_FAILED [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
