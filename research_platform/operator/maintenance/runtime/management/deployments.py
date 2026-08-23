from __future__ import annotations

import json
from pathlib import Path
import sys

from research_platform.model.deployment.api import (
    ModelDeploymentSelector,
    ModelDeploymentSpec,
    ModelDesiredState,
)
from research_platform.model.qualification.api import (
    DeploymentQualificationApplicationRequest,
    DeploymentQualificationRequest,
    DeploymentQualificationRuntimeRequest,
)

from .context import ManagementCommandContext
from .scope_args import scope_from_json

GROUP = "deployment"


def _qualification_python_path(path: Path) -> Path:
    """Keep the environment entrypoint instead of resolving its symlink."""

    return path.expanduser()


def _deployment_from_json(path: Path) -> ModelDeploymentSpec:
    data = json.loads(path.read_text("utf-8"))
    return ModelDeploymentSpec(
        deployment_id=data["deployment_id"],
        scope=scope_from_json(data.get("scope")),
        service_id=data.get("service_id", f"model:{data['deployment_id']}"),
        model_id=data["model_id"],
        engine=data.get("engine", "custom"),
        executable=data["executable"],
        argv=tuple(data.get("argv", ())),
        cwd=Path(data["cwd"]).expanduser().resolve(),
        python_environment_id=data.get("python_environment_id"),
        gpu_devices=tuple(str(value) for value in data.get("gpu_devices", ())),
        environment=tuple(sorted((str(k), str(v)) for k, v in data.get("environment", {}).items())),
        readiness_url=data.get("readiness_url"),
        readiness_timeout_s=float(data.get("readiness_timeout_s", 120.0)),
        stop_timeout_s=float(data.get("stop_timeout_s", 30.0)),
        heartbeat_interval_s=float(data.get("heartbeat_interval_s", 10.0)),
        desired_state=ModelDesiredState(data.get("desired_state", "stopped")),
        tags=tuple(sorted({str(value) for value in data.get("tags", ()) if str(value)})),
    )


def _selector(args) -> ModelDeploymentSelector:
    return ModelDeploymentSelector(
        tags=tuple(getattr(args, "tag", ())),
        model_id=getattr(args, "model", None),
        engine=getattr(args, "engine", None),
        python_environment_id=getattr(args, "env", None),
    )


def register(groups) -> None:
    parser = groups.add_parser(GROUP)
    sub = parser.add_subparsers(dest="action", required=True)
    put_json = sub.add_parser("put-json")
    put_json.add_argument("path", type=Path)
    listing = sub.add_parser("list")
    for target in (listing,):
        target.add_argument("--tag", action="append", default=[])
        target.add_argument("--model")
        target.add_argument("--engine")
        target.add_argument("--env")
    desire = sub.add_parser("desire")
    desire.add_argument("deployment_id")
    desire.add_argument("state", choices=("running", "stopped"))
    desire_all = sub.add_parser("desire-all")
    desire_all.add_argument("state", choices=("running", "stopped"))
    desire_all.add_argument("--tag", action="append", default=[])
    desire_all.add_argument("--model")
    desire_all.add_argument("--engine")
    desire_all.add_argument("--env")
    for action in ("start", "stop", "restart", "status", "remove"):
        command = sub.add_parser(action)
        command.add_argument("deployment_id")
    set_gpus = sub.add_parser("set-gpus")
    set_gpus.add_argument("deployment_id")
    set_gpus.add_argument("gpu_devices", nargs="*")
    set_env = sub.add_parser("set-env")
    set_env.add_argument("deployment_id")
    set_env.add_argument("environment_id", nargs="?")
    for action in ("status-all", "reconcile", "start-all", "stop-all", "gpu", "gpu-conflicts", "gpu-runtime", "env-usage", "gpu-processes"):
        sub.add_parser(action)
    candidates = sub.add_parser("gpu-candidates")
    candidates.add_argument("--count", type=int, default=1)
    candidates.add_argument("--min-free-mb", type=int, default=0)
    candidates.add_argument("--max-utilization", type=int, default=100)
    logs = sub.add_parser("logs")
    logs.add_argument("deployment_id")
    tail = sub.add_parser("tail")
    tail.add_argument("deployment_id")
    tail.add_argument("--stream", choices=("stdout", "stderr"), default="stderr")
    tail.add_argument("--max-bytes", type=int, default=8192)
    qualify = sub.add_parser("qualify")
    qualify.add_argument("--model-id", required=True)
    qualify.add_argument("--model-path", required=True, type=Path)
    qualify.add_argument(
        "--environment-id",
        help="resolve the target interpreter from the platform Python-environment registry",
    )
    qualify.add_argument(
        "--python",
        type=Path,
        help="direct interpreter path for an environment not registered with the platform",
    )
    qualify.add_argument("--backend", action="append", dest="backends", default=[])
    qualify.add_argument("--tensor-parallel", type=int, default=1)
    qualify.add_argument("--index-url", action="append", dest="index_urls", default=[])
    qualify.add_argument("--timeout-seconds", type=float, default=30.0)
    qualification = sub.add_parser("qualification")
    qualification.add_argument("plan_digest")
    apply_qualification = sub.add_parser("apply-qualification")
    apply_qualification.add_argument("plan_digest")
    apply_qualification.add_argument("--environment-id", required=True)
    runtime_qualification = sub.add_parser("runtime-qualify")
    runtime_qualification.add_argument("application_digest")


def dispatch(args, context: ManagementCommandContext):
    catalog = context.models.deployment_catalog
    runtime = context.models.deployment_runtime
    fleet = context.models.fleet
    logs = context.models.deployment_logs
    resources = context.models.resources
    action = args.action
    if action == "put-json":
        return catalog.put_deployment(_deployment_from_json(args.path))
    if action == "list":
        return catalog.select(_selector(args))
    if action == "desire":
        return catalog.set_desired_state(args.deployment_id, ModelDesiredState(args.state))
    if action == "desire-all":
        return catalog.set_desired_state_selected(_selector(args), ModelDesiredState(args.state))
    if action == "start":
        return runtime.start(args.deployment_id)
    if action == "stop":
        return runtime.stop(args.deployment_id)
    if action == "restart":
        return runtime.restart(args.deployment_id)
    if action == "set-gpus":
        return catalog.set_gpu_devices(args.deployment_id, tuple(args.gpu_devices))
    if action == "set-env":
        return catalog.set_python_environment(args.deployment_id, args.environment_id)
    if action == "status":
        return runtime.status(args.deployment_id)
    if action == "remove":
        return {"removed": runtime.remove_deployment(args.deployment_id)}
    if action == "status-all":
        return fleet.status_all()
    if action == "reconcile":
        return fleet.reconcile()
    if action == "start-all":
        return fleet.start_all()
    if action == "stop-all":
        return fleet.stop_all()
    if action == "gpu":
        return resources.gpu_allocations()
    if action == "gpu-conflicts":
        return resources.gpu_conflicts()
    if action == "gpu-runtime":
        return resources.gpu_runtime()
    if action == "gpu-candidates":
        return resources.gpu_candidates(
            count=args.count,
            min_free_memory_mb=args.min_free_mb,
            max_utilization_percent=args.max_utilization,
        )
    if action == "env-usage":
        return resources.environment_usage()
    if action == "gpu-processes":
        return resources.gpu_process_bindings()
    if action == "logs":
        return logs.logs(args.deployment_id)
    if action == "tail":
        return logs.tail_logs(args.deployment_id, stream=args.stream, max_bytes=args.max_bytes)
    if action == "qualify":
        if args.environment_id and args.python:
            raise ValueError("deployment qualification accepts either --environment-id or --python, not both")
        environment_id = args.environment_id
        if environment_id:
            python_path = context.environments.lifecycle.get(environment_id).python_path
        else:
            python_path = args.python or Path(sys.executable)
        return context.deployment_qualification.qualification.qualify(
            DeploymentQualificationRequest(
                model_id=args.model_id,
                model_path=args.model_path.expanduser().resolve(),
                # Do not resolve symlinks here.  A venv's bin/python commonly
                # points at the system interpreter; resolving it loses the
                # selected environment's site-packages and kernel extensions.
                python_executable=_qualification_python_path(python_path),
                python_environment_id=environment_id,
                backends=tuple(args.backends) if args.backends else ("sglang", "vllm"),
                tensor_parallel=args.tensor_parallel,
                package_index_urls=tuple(args.index_urls) if args.index_urls else ("https://pypi.org/simple",),
                probe_timeout_seconds=args.timeout_seconds,
            )
        )
    if action == "qualification":
        return context.deployment_qualification.evidence.get(args.plan_digest)
    if action == "apply-qualification":
        return context.deployment_qualification.application.apply(
            DeploymentQualificationApplicationRequest(
                plan_digest=args.plan_digest,
                environment_id=args.environment_id,
            )
        )
    if action == "runtime-qualify":
        return context.deployment_qualification.runtime.qualify(
            DeploymentQualificationRuntimeRequest(args.application_digest)
        )
    raise ValueError(f"unsupported deployment management action: {action}")


__all__ = ["GROUP", "dispatch", "register"]
