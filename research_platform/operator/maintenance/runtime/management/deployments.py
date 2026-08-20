from __future__ import annotations

import json
from pathlib import Path

from research_platform.model.deployment.api import (
    ModelDeploymentSelector,
    ModelDeploymentSpec,
    ModelDesiredState,
)

from .context import ManagementCommandContext
from .scope_args import scope_from_json

GROUP = "deployment"


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
    raise ValueError(f"unsupported deployment management action: {action}")


__all__ = ["GROUP", "dispatch", "register"]
