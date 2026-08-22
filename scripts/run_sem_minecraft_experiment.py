"""Run the current SEM Minecraft production graph.

This is the experiment entrypoint for the current repository.  It composes the
project and platform seams explicitly, starts one source Minecraft service,
captures a verified world cut, and evaluates a control branch from that cut.
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
import shutil
import sys
import threading
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
    task_from_mapping,
)
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from projects.sem_paper.method.self_evolving_memory.session_evolution_runtime import (
    DisabledSessionEvolutionFactory,
)
from projects.sem_paper.method.self_evolving_memory.minecraft_transform import (
    MinecraftGroundedSemanticTransformer,
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
from research_platform.model.request.prompt.composition import FrozenPromptRequestBinding
from research_platform.model.request.prompt.runtime import (
    PromptRegistry,
    default_block_policies,
    default_output_schemas,
    default_prompt_specs,
)
from research_platform.model.request.runtime import (
    DirectoryContentAddressedStore,
    DirectoryModelRequestLedger,
    ReconstructableModelRequestRecorder,
)
from research_platform.model.serving.endpoint.api import ModelEndpointRoute
from research_platform.model.serving.endpoint.providers import (
    OpenAICompatibleModelEndpoint,
    UrllibJsonTransport,
)
from research_platform.observability.logging.composition import (
    LogQueryBinding,
    LogSinkBinding,
    compose_logging_system,
)
from research_platform.observability.logging.storage.runtime import InMemoryLogStore
from research_platform.participant.method.composition import compose_default_method_system
from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity, canonical_digest
from research_platform.runtime.host.composition import compose_local_host
from research_platform.runtime.host.providers import LocalOperatingSystemRoute
from research_platform.runtime.service.runtime.environment import MaterializedServiceEnvironment
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind


class ExperimentConfigurationError(ValueError):
    """The live experiment inputs are incomplete or inconsistent."""


class JsonlAppender:
    """Small append-only evidence sink used by the experiment composition."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def append(self, value: Mapping[str, object]) -> None:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())


def _json_default(value: object) -> object:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    return repr(value)


class ExperimentDiagnostics:
    """One append-only diagnostic adapter for MC and Paper workload ports."""

    def __init__(self, root: Path) -> None:
        self.events = JsonlAppender(root / "events.jsonl")
        self.metrics = JsonlAppender(root / "metrics.jsonl")
        self.failures = JsonlAppender(root / "failures.jsonl")

    def event(self, *args: object, **kwargs: object) -> None:
        if args and "phase" not in kwargs:
            event = str(args[0])
            phase = "workload"
            attributes = kwargs.get("attributes", {})
            level = str(kwargs.get("level", "DEBUG"))
            correlation_refs: tuple[str, ...] = ()
        else:
            phase = str(kwargs.get("phase", "minecraft"))
            event = str(kwargs.get("event", ""))
            attributes = kwargs.get("attributes", {})
            level = str(kwargs.get("level", "DEBUG"))
            correlation_refs = tuple(str(x) for x in kwargs.get("correlation_refs", ()))
        self.events.append(
            {
                "kind": "event",
                "phase": phase,
                "event": event,
                "level": level,
                "attributes": dict(attributes) if isinstance(attributes, Mapping) else repr(attributes),
                "correlation_refs": correlation_refs,
            }
        )

    def metric(self, *args: object, **kwargs: object) -> None:
        name = str(kwargs.get("name", args[0] if args else ""))
        value = float(kwargs.get("value", args[1] if len(args) > 1 else 0.0))
        labels = kwargs.get("labels", {})
        self.metrics.append(
            {
                "kind": "metric",
                "name": name,
                "value": value,
                "labels": dict(labels) if isinstance(labels, Mapping) else repr(labels),
            }
        )

    def failure(self, *args: object, **kwargs: object) -> None:
        if args:
            code = str(args[0])
            message = str(args[1]) if len(args) > 1 else ""
            phase = str(kwargs.get("phase", "workload"))
            exception = None
        else:
            phase = str(kwargs.get("phase", "minecraft"))
            code = str(kwargs.get("code", ""))
            message = str(kwargs.get("message", ""))
            exception = kwargs.get("exception")
        self.failures.append(
            {
                "kind": "failure",
                "phase": phase,
                "code": code,
                "message": message,
                "exception_type": type(exception).__name__ if exception is not None else None,
                "attributes": dict(kwargs.get("attributes", {})) if isinstance(kwargs.get("attributes", {}), Mapping) else {},
                "correlation_refs": tuple(str(x) for x in kwargs.get("correlation_refs", ())),
            }
        )


class JsonlMethodObservationSink:
    def __init__(self, path: Path) -> None:
        self._rows = JsonlAppender(path)

    def record(self, observation: object) -> None:
        self._rows.append({"observation": observation})


class _BranchEnvironmentFactory:
    def __init__(self, *, operating_system: LocalOperatingSystemRoute, diagnostics: ExperimentDiagnostics) -> None:
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


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or not value.strip():
        raise ExperimentConfigurationError(f"required environment variable is missing: {name}")
    return value.strip()


def _resolve_executable(value: str, *, variable: str) -> str:
    candidate = Path(value).expanduser()
    resolved = candidate if candidate.is_absolute() else Path(shutil.which(value) or "")
    if not str(resolved) or not resolved.is_file():
        raise ExperimentConfigurationError(f"{variable} does not resolve to an executable: {value}")
    return str(resolved.resolve())


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
    parser.add_argument("--tasks", type=Path, default=None)
    parser.add_argument("--task-ids", default=os.environ.get("SEM_MC_TASK_IDS", ""))
    parser.add_argument("--accept-minecraft-eula", action="store_true")
    parser.add_argument("--rcon-password-env", default=os.environ.get("SEM_MC_RCON_PASSWORD_ENV", "SEM_MC_RCON_PASSWORD"))
    args = parser.parse_args(argv)

    repo_root = _REPOSITORY_ROOT
    run_id = args.run_id.strip() or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = (args.output_dir or repo_root / "runs" / "sem_paper" / run_id).resolve()
    server_jar = Path(args.server_jar or os.environ.get("SEM_MC_SERVER_JAR", "")).expanduser().resolve()
    bridge_dir = Path(args.bridge_dir or os.environ.get("SEM_MC_BRIDGE_DIR", repo_root / "research_platform" / "environment" / "minecraft" / "providers" / "assets" / "mineflayer_bridge")).expanduser().resolve()
    source_workdir = Path(args.source_workdir or os.environ.get("SEM_MC_SOURCE_WORKDIR", output / "source-server")).expanduser().resolve()
    snapshot_root = Path(args.snapshot_root or os.environ.get("SEM_MC_SNAPSHOT_ROOT", output / "world-cuts")).expanduser().resolve()
    branch_root = Path(args.branch_root or os.environ.get("SEM_MC_BRANCH_ROOT", output / "branches")).expanduser().resolve()
    tasks_path = Path(args.tasks or os.environ.get("SEM_MC_TASKS", repo_root / "projects" / "sem_paper" / "experiments" / "manifests" / "dev_neutral.json")).expanduser().resolve()
    node = args.node_executable.strip() or shutil.which("node") or ""
    java = args.java_executable.strip() or shutil.which("java") or ""
    model_base_url = args.model_base_url.strip()
    model_id = args.model_id.strip()
    if args.mode == "baseline" and (not model_base_url or not model_id):
        raise ExperimentConfigurationError("baseline requires SEM_MC_MODEL_BASE_URL and SEM_MC_MODEL_ID")
    if not java:
        raise ExperimentConfigurationError("Java executable is not resolvable; set SEM_MC_JAVA")
    if not node:
        raise ExperimentConfigurationError("Node executable is not resolvable; set SEM_MC_NODE")
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
        node_executable=_resolve_executable(node, variable="SEM_MC_NODE"),
        java_executable=_resolve_executable(java, variable="SEM_MC_JAVA"),
        model_base_url=model_base_url,
        model_id=model_id,
        model_family=args.model_family,
        model_timeout_s=args.model_timeout_s,
        model_context_length=args.model_context_length,
        tasks_path=tasks_path,
        task_ids=task_ids,
        accept_eula=bool(args.accept_minecraft_eula),
        rcon_password_env=args.rcon_password_env,
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
    tasks = tuple(task_from_mapping(row) for row in raw["tasks"] if isinstance(row, Mapping))
    if len(tasks) != len(raw["tasks"]):
        raise ExperimentConfigurationError("task manifest contains a non-mapping task")
    if selected:
        by_id = {task.task_id: task for task in tasks}
        missing = tuple(task_id for task_id in selected if task_id not in by_id)
        if missing:
            raise ExperimentConfigurationError(f"requested task ids are missing: {missing}")
        tasks = tuple(by_id[task_id] for task_id in selected)
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


def _build_planner(inputs: ExperimentInputs, output: Path):
    if inputs.mode == "scripted-smoke":
        class ScriptedFactory:
            def create(self, *, role, candidate, task, method):
                del role, candidate, method
                script = task.script or ({"tool": "finish", "args": {"reason": "scripted_smoke"}},)
                return ScriptedMinecraftPlanner(tuple(script))
        return ScriptedFactory()

    registry = PromptRegistry()
    registry.publish("sem-paper-planner-generation-v1", default_prompt_specs(inputs.model_family))
    recorder = ReconstructableModelRequestRecorder(
        DirectoryContentAddressedStore(output / "model" / "blobs"),
        DirectoryModelRequestLedger(output / "model" / "requests"),
    )
    prompt_binding = FrozenPromptRequestBinding(
        registry=registry,
        prompt_id="planner.v6",
        policy=default_block_policies()["planner"],
        schemas=default_output_schemas(),
        model_requests=recorder,
    )
    deployment_id = "sem-paper-planner"
    deployment_generation = canonical_digest(
        {
            "deployment_id": deployment_id,
            "base_url": inputs.model_base_url,
            "model_id": inputs.model_id,
            "prompt_generation": prompt_binding.prompt_generation_id,
        }
    )
    headers: tuple[tuple[str, str], ...] = ()
    api_key = os.environ.get("SEM_MC_MODEL_API_KEY", "")
    if api_key:
        headers = (("Authorization", f"Bearer {api_key}"),)
    endpoint = OpenAICompatibleModelEndpoint(
        route=ModelEndpointRoute(
            deployment_id=deployment_id,
            deployment_generation=deployment_generation,
            base_url=inputs.model_base_url,
            timeout_s=inputs.model_timeout_s,
        ),
        transport=UrllibJsonTransport(headers=headers),
    )
    model = ImmutableModelIdentity(
        logical_name="sem-paper-planner",
        model_id=inputs.model_id,
        revision=os.environ.get("SEM_MC_MODEL_REVISION", "operator-declared"),
        engine=os.environ.get("SEM_MC_MODEL_ENGINE", "openai-compatible"),
        engine_version=os.environ.get("SEM_MC_MODEL_ENGINE_VERSION", "operator-declared"),
        dtype=os.environ.get("SEM_MC_MODEL_DTYPE", "bfloat16"),
        quantization=os.environ.get("SEM_MC_MODEL_QUANTIZATION") or None,
        context_length=inputs.model_context_length,
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


def build_runtime(inputs: ExperimentInputs, tasks: tuple[MinecraftTaskSpec, ...], diagnostics: ExperimentDiagnostics):
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
    evolution_factory = DisabledSessionEvolutionFactory()
    candidate_method_materializer = SemPaperCandidateMethodMaterializer(
        method_system=method_system.ports,
        evolution_factory=evolution_factory,
        evolution_provider_id="sem.evolution.disabled.candidate.v1",
        transformer=MinecraftGroundedSemanticTransformer(),
    )
    project = compose_sem_paper(
        SemPaperCompositionPorts(
            method_system=method_system,
            logging=logging,
            planner=meta.capability_composition,
            scope=project_scope,
            evolution_factory=evolution_factory,
            evolution_provider_id="sem.evolution.disabled.experimental-baseline.v1",
            candidate_method_materializer=candidate_method_materializer,
        )
    )
    host = compose_local_host(planner=meta.capability_composition)
    os_route = host.operating_system
    service_environment = _service_environment()
    server_config = MinecraftServerServiceFactoryConfig(
        environment=service_environment,
        state_root=inputs.output_dir / "service-state",
        intent_root=inputs.output_dir / "service-intents",
        capture_root=inputs.output_dir / "service-captures",
        operating_system=os_route,
        accept_eula=inputs.accept_eula,
    )
    branch_server_factory = MinecraftServerServiceFactory(server_config)
    source_rcon = MinecraftRconEndpoint(host=inputs.server_host, port=inputs.source_rcon_port)
    source_spec = MinecraftServerSpec(
        jar_path=str(inputs.server_jar),
        workdir=str(inputs.source_workdir),
        java_executable=inputs.java_executable,
        host=inputs.server_host,
        port=inputs.source_port,
        level_name="sem-paper-source-world",
        level_seed=inputs.server_seed,
        rcon_endpoint=source_rcon,
    )
    password = os.environ.get(inputs.rcon_password_env, "")
    if not password:
        raise ExperimentConfigurationError(f"RCON secret is missing in environment variable {inputs.rcon_password_env}")
    source_config = MinecraftServerServiceFactoryConfig(
        environment=service_environment,
        state_root=inputs.output_dir / "source-service-state",
        intent_root=inputs.output_dir / "source-service-intents",
        capture_root=inputs.output_dir / "source-service-captures",
        operating_system=os_route,
        accept_eula=inputs.accept_eula,
        rcon_password_provider=lambda: password,
    )
    source_server_factory = MinecraftServerServiceFactory(source_config)
    console = MinecraftRconConsole(source_rcon, secret_provider=lambda: password)
    bridge_path = inputs.bridge_dir / "bridge.js"
    environment_template = MinecraftEnvironmentSpec(
        endpoint=MinecraftEndpointSpec(inputs.server_host, inputs.source_port),
        bridge=MinecraftBridgeSpec((inputs.node_executable, str(bridge_path)), str(inputs.bridge_dir), stderr_log_path=str(inputs.output_dir / "bridge.stderr.log")),
        agent=MinecraftAgentSpec(username=inputs.minecraft_username, version=inputs.minecraft_version),
    )
    branch_template = MinecraftServerSpec(
        jar_path=str(inputs.server_jar),
        workdir=str(inputs.source_workdir),
        java_executable=inputs.java_executable,
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
    planner_factory = _build_planner(inputs, inputs.output_dir)
    observation_sink = JsonlMethodObservationSink(inputs.output_dir / "method_observations.jsonl")

    class ObservationSinkFactory:
        def create(self, *, role, branch):
            del role, branch
            return observation_sink

    root = compose_sem_paper_minecraft_production_root(
        composition=project,
        world_cuts=host.world_cuts,
        branch_runtime_factory=host.branch_runtime_factory,
        request_factory=request_factory,
        planner_factory=planner_factory,
        observation_sink_factory=ObservationSinkFactory(),
        tasks=tasks,
        context=context,
        workload_id_factory=lambda role, branch: f"sem-paper:{role.value}:{branch.branch_id}",
        session_id=f"{inputs.run_id}:source-cut",
        branch_id_factory=lambda role: f"{inputs.run_id}:{role.value}",
        destination_factory=lambda branch_id: str(inputs.branch_root / branch_id.replace(":", "_")),
        diagnostics=diagnostics,
    )
    return root, host, log_store


def _write_manifest(inputs: ExperimentInputs, tasks: tuple[MinecraftTaskSpec, ...], candidate) -> None:
    inputs.output_dir.mkdir(parents=True, exist_ok=True)
    safe = asdict(inputs)
    safe.pop("output_dir", None)
    safe["server_jar"] = str(inputs.server_jar)
    safe["bridge_dir"] = str(inputs.bridge_dir)
    safe["source_workdir"] = str(inputs.source_workdir)
    safe["snapshot_root"] = str(inputs.snapshot_root)
    safe["branch_root"] = str(inputs.branch_root)
    safe["tasks_path"] = str(inputs.tasks_path)
    safe["rcon_password_env"] = inputs.rcon_password_env
    safe["tasks"] = [asdict(task) for task in tasks]
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
    (inputs.output_dir / "run_manifest.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")


def run(inputs: ExperimentInputs) -> int:
    if sys.version_info < (3, 11):
        raise ExperimentConfigurationError("current research-platform requires Python >= 3.11")
    if not inputs.server_jar.is_file():
        raise ExperimentConfigurationError(f"Minecraft server.jar is missing: {inputs.server_jar}")
    if not (inputs.bridge_dir / "bridge.js").is_file():
        raise ExperimentConfigurationError(f"Mineflayer bridge.js is missing: {inputs.bridge_dir}")
    tasks = load_tasks(inputs.tasks_path, inputs.task_ids)
    candidate = build_seed_x_candidate()
    _write_manifest(inputs, tasks, candidate)
    if inputs.mode == "preflight":
        probes = minecraft_preflight(
            inputs.bridge_dir,
            host=inputs.server_host,
            port=inputs.source_port,
            check_server=False,
            node_command=inputs.node_executable,
            java_command=inputs.java_executable,
        )
        (inputs.output_dir / "preflight.json").write_text(report_json(probes) + "\n", encoding="utf-8")
        if not all(probe.ok for probe in probes):
            failed = ", ".join(f"{probe.name}:{probe.cause_code}" for probe in probes if not probe.ok)
            raise ExperimentConfigurationError(f"Minecraft preflight failed: {failed}")
        result = {"run_id": inputs.run_id, "mode": inputs.mode, "status": "preflight_ok", "task_count": len(tasks)}
        (inputs.output_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    if not LocalOperatingSystemRoute().is_posix:
        raise ExperimentConfigurationError(
            "live Minecraft launch requires a POSIX host with the exact Linux process provider; "
            "run this entrypoint on the Ubuntu target"
        )
    diagnostics = ExperimentDiagnostics(inputs.output_dir)
    root, host, log_store = build_runtime(inputs, tasks, diagnostics)
    started = False
    result: dict[str, object] = {"run_id": inputs.run_id, "mode": inputs.mode, "status": "started"}
    try:
        host.start_source()
        started = True
        root.branch_runner.prepare_source_cut()
        evaluation = root.evaluator.evaluate_with_receipts(candidate)
        result.update(
            {
                "status": "completed",
                "scientific_claim": inputs.mode == "baseline" and evaluation.proof.comparability.valid,
                "scientific_scope": (
                    "paired_control_vs_seed_x_v018_model_backed"
                    if inputs.mode == "baseline"
                    else "paired_control_vs_seed_x_v018_plumbing_only"
                ),
                "candidate": {
                    "candidate_id": candidate.candidate_id,
                    "target_spec_digest": candidate.target_spec_digest,
                },
                "control_receipt": evaluation.control,
                "candidate_receipt": evaluation.candidate,
                "evaluation_proof": evaluation.proof,
            }
        )
        (inputs.output_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
        return 0
    except BaseException as exc:
        result.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        (inputs.output_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
        raise
    finally:
        if started:
            host.stop_source()
        if log_store is not None:
            rows = [row.to_dict() for row in log_store.query(limit=100000)]
            (inputs.output_dir / "logs.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_inputs(argv))
    except Exception as exc:
        print(f"SEM_MINECRAFT_EXPERIMENT_FAILED [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
