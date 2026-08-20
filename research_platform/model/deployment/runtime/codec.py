from __future__ import annotations
import json
from pathlib import Path
from research_platform.model.deployment.api import ModelDeploymentSpec, ModelDesiredState
from research_platform.runtime.service.api import ServiceLaunchContract
from research_platform.scope.api import scope_from_data, scope_to_data
from .applied import AppliedModelDeployment

def deployment_to_data(value: ModelDeploymentSpec) -> dict[str, object]:
    return {
        "deployment_id": value.deployment_id, "scope": scope_to_data(value.scope), "service_id": value.service_id,
        "model_id": value.model_id, "engine": value.engine, "executable": value.executable, "argv": list(value.argv),
        "cwd": str(value.cwd), "python_environment_id": value.python_environment_id, "gpu_devices": list(value.gpu_devices),
        "environment": [list(row) for row in value.environment], "readiness_url": value.readiness_url,
        "readiness_timeout_s": value.readiness_timeout_s, "stop_timeout_s": value.stop_timeout_s,
        "heartbeat_interval_s": value.heartbeat_interval_s, "desired_state": value.desired_state.value, "tags": list(value.tags),
    }

def encode_deployment(value: ModelDeploymentSpec) -> bytes:
    return json.dumps(deployment_to_data(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def decode_deployment(data: dict[str, object]) -> ModelDeploymentSpec:
    return ModelDeploymentSpec(
        deployment_id=str(data["deployment_id"]), scope=scope_from_data(data["scope"]), service_id=str(data["service_id"]),
        model_id=str(data["model_id"]), engine=str(data["engine"]), executable=str(data["executable"]),
        argv=tuple(str(item) for item in data["argv"]), cwd=Path(str(data["cwd"])),
        python_environment_id=(str(data["python_environment_id"]) if data.get("python_environment_id") is not None else None),
        gpu_devices=tuple(str(item) for item in data.get("gpu_devices", ())),
        environment=tuple((str(row[0]), str(row[1])) for row in data.get("environment", ())),
        readiness_url=(str(data["readiness_url"]) if data.get("readiness_url") is not None else None),
        readiness_timeout_s=float(data.get("readiness_timeout_s", 120.0)), stop_timeout_s=float(data.get("stop_timeout_s", 30.0)),
        heartbeat_interval_s=float(data.get("heartbeat_interval_s", 10.0)),
        desired_state=ModelDesiredState(str(data.get("desired_state", "stopped"))), tags=tuple(str(item) for item in data.get("tags", ())),
    )

def encode_applied(value: AppliedModelDeployment) -> bytes:
    contract = value.contract
    payload = {"spec": deployment_to_data(value.spec), "contract": {
        "service_id": contract.service_id, "generation": contract.generation, "executable": contract.executable,
        "argv": list(contract.argv), "cwd": contract.cwd, "environment_digest": contract.environment_digest,
        "artifact_digest": contract.artifact_digest, "runtime_identity_digest": contract.runtime_identity_digest,
        "readiness_timeout_s": contract.readiness_timeout_s, "stop_timeout_s": contract.stop_timeout_s,
        "heartbeat_interval_s": contract.heartbeat_interval_s,
    }, "environment": [list(row) for row in value.environment]}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def decode_applied(data: dict[str, object]) -> AppliedModelDeployment:
    spec = decode_deployment(data["spec"])
    contract_data = data["contract"]
    contract = ServiceLaunchContract(
        service_id=str(contract_data["service_id"]), generation=str(contract_data["generation"]), executable=str(contract_data["executable"]),
        argv=tuple(str(item) for item in contract_data["argv"]), cwd=str(contract_data["cwd"]),
        environment_digest=str(contract_data["environment_digest"]), artifact_digest=str(contract_data["artifact_digest"]),
        runtime_identity_digest=str(contract_data["runtime_identity_digest"]), readiness_timeout_s=float(contract_data["readiness_timeout_s"]),
        stop_timeout_s=float(contract_data["stop_timeout_s"]), heartbeat_interval_s=float(contract_data["heartbeat_interval_s"]),
    )
    environment = tuple((str(row[0]), str(row[1])) for row in data.get("environment", ()))
    return AppliedModelDeployment(spec, contract, environment)

__all__ = ["decode_applied", "decode_deployment", "deployment_to_data", "encode_applied", "encode_deployment"]
