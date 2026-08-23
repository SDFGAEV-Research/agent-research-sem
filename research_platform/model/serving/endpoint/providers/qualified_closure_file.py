from __future__ import annotations

"""Durable reader for the qualified model deployment closure.

The reader is deliberately read-only.  Qualification and deployment systems
publish the closure; a project may only consume the reconstructed typed
projection.  No value in this document is inferred from an operator URL,
model name, or live readiness probe.
"""

from dataclasses import dataclass
from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from research_platform.model.serving.api import (
    DeploymentPlacement,
    QualificationCertificate,
    QualifiedDeploymentManifest,
    ResourceEnvelope,
    RoleModelAssignment,
    RoleModelManifest,
    RuntimeQualificationEvidenceStorePort,
)
from research_platform.model.stack.api import (
    ModelArtifactClosure,
    ModelStackSpec,
    RuntimeBuildIdentity,
)
from research_platform.platform.kernel import ImmutableModelIdentity

from ..api import ModelEndpointRoute
from .qualified_binding import QualifiedModelDeploymentClosure


_SCHEMA = "qualified-model-deployment-closure.v1"


class QualifiedModelClosureReadError(ValueError):
    """The persisted closure is absent, malformed, or internally inconsistent."""


def _mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QualifiedModelClosureReadError(f"closure field must be an object: {field}")
    return value


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualifiedModelClosureReadError(f"closure field must be a non-empty string: {field}")
    return value


def _optional_string(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _string(value, field=field)


def _tuple_strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise QualifiedModelClosureReadError(f"closure field must be a non-empty string list: {field}")
    return tuple(value)


def _identity(raw: object, *, field: str) -> ImmutableModelIdentity:
    value = _mapping(raw, field=field)
    try:
        return ImmutableModelIdentity(
            logical_name=_string(value.get("logical_name"), field=f"{field}.logical_name"),
            model_id=_string(value.get("model_id"), field=f"{field}.model_id"),
            revision=_string(value.get("revision"), field=f"{field}.revision"),
            engine=_string(value.get("engine"), field=f"{field}.engine"),
            engine_version=_string(value.get("engine_version"), field=f"{field}.engine_version"),
            dtype=_string(value.get("dtype"), field=f"{field}.dtype"),
            quantization=_optional_string(value.get("quantization"), field=f"{field}.quantization"),
            context_length=int(value.get("context_length")),
            tokenizer_revision=_optional_string(value.get("tokenizer_revision"), field=f"{field}.tokenizer_revision"),
        )
    except (TypeError, ValueError) as exc:
        raise QualifiedModelClosureReadError(f"invalid model identity: {field}") from exc


def _stack(raw: object, *, field: str) -> ModelStackSpec:
    value = _mapping(raw, field=field)
    artifacts = _mapping(value.get("artifacts"), field=f"{field}.artifacts")
    runtime = _mapping(value.get("runtime"), field=f"{field}.runtime")
    try:
        return ModelStackSpec(
            identity=_identity(value.get("identity"), field=f"{field}.identity"),
            artifacts=ModelArtifactClosure(
                weights_manifest_sha256=_string(artifacts.get("weights_manifest_sha256"), field=f"{field}.artifacts.weights_manifest_sha256"),
                tokenizer_sha256=_string(artifacts.get("tokenizer_sha256"), field=f"{field}.artifacts.tokenizer_sha256"),
                model_config_sha256=_string(artifacts.get("model_config_sha256"), field=f"{field}.artifacts.model_config_sha256"),
                model_code_sha256=_optional_string(artifacts.get("model_code_sha256"), field=f"{field}.artifacts.model_code_sha256"),
                chat_template_sha256=_optional_string(artifacts.get("chat_template_sha256"), field=f"{field}.artifacts.chat_template_sha256"),
            ),
            runtime=RuntimeBuildIdentity(
                container_digest=_string(runtime.get("container_digest"), field=f"{field}.runtime.container_digest"),
                engine_build_digest=_string(runtime.get("engine_build_digest"), field=f"{field}.runtime.engine_build_digest"),
                python_lock_digest=_string(runtime.get("python_lock_digest"), field=f"{field}.runtime.python_lock_digest"),
                cuda_runtime=_string(runtime.get("cuda_runtime"), field=f"{field}.runtime.cuda_runtime"),
                nccl_version=_string(runtime.get("nccl_version"), field=f"{field}.runtime.nccl_version"),
                torch_version=_string(runtime.get("torch_version"), field=f"{field}.runtime.torch_version"),
                kernel_extensions_digest=_string(runtime.get("kernel_extensions_digest"), field=f"{field}.runtime.kernel_extensions_digest"),
            ),
            tensor_parallel=int(value.get("tensor_parallel")),
            data_parallel=int(value.get("data_parallel")),
            expert_parallel=int(value.get("expert_parallel")),
            pipeline_parallel=int(value.get("pipeline_parallel")),
            reasoning_parser=_optional_string(value.get("reasoning_parser"), field=f"{field}.reasoning_parser"),
            tool_call_parser=_optional_string(value.get("tool_call_parser"), field=f"{field}.tool_call_parser"),
            kv_cache_dtype=_optional_string(value.get("kv_cache_dtype"), field=f"{field}.kv_cache_dtype"),
            attention_backend=_optional_string(value.get("attention_backend"), field=f"{field}.attention_backend"),
            scheduler_policy=_string(value.get("scheduler_policy"), field=f"{field}.scheduler_policy"),
            engine_args=tuple(value.get("engine_args", ())),
        )
    except (TypeError, ValueError) as exc:
        raise QualifiedModelClosureReadError(f"invalid model stack: {field}") from exc


def _certificate(raw: object, *, field: str) -> QualificationCertificate:
    value = _mapping(raw, field=field)
    envelope = _mapping(value.get("resource_envelope"), field=f"{field}.resource_envelope")
    try:
        return QualificationCertificate(
            model_stack_digest=_string(value.get("model_stack_digest"), field=f"{field}.model_stack_digest"),
            evidence_digest=_string(value.get("evidence_digest"), field=f"{field}.evidence_digest"),
            qualified_roles=_tuple_strings(value.get("qualified_roles"), field=f"{field}.qualified_roles"),
            resource_envelope=ResourceEnvelope(
                peak_gpu_memory_bytes_per_device=int(envelope.get("peak_gpu_memory_bytes_per_device")),
                peak_host_memory_bytes=int(envelope.get("peak_host_memory_bytes")),
                max_qualified_concurrency=int(envelope.get("max_qualified_concurrency")),
                ttft_p99_seconds=float(envelope.get("ttft_p99_seconds")),
                tpot_p99_seconds=float(envelope.get("tpot_p99_seconds")),
                minimum_output_tokens_per_second=float(envelope.get("minimum_output_tokens_per_second")),
            ),
            target_host_identity_digest=_string(value.get("target_host_identity_digest"), field=f"{field}.target_host_identity_digest"),
        )
    except (TypeError, ValueError) as exc:
        raise QualifiedModelClosureReadError(f"invalid qualification certificate: {field}") from exc


def _deployment(raw: object, *, field: str) -> QualifiedDeploymentManifest:
    value = _mapping(raw, field=field)
    placement = _mapping(value.get("placement"), field=f"{field}.placement")
    try:
        return QualifiedDeploymentManifest(
            deployment_id=_string(value.get("deployment_id"), field=f"{field}.deployment_id"),
            stack=_stack(value.get("stack"), field=f"{field}.stack"),
            certificate=_certificate(value.get("certificate"), field=f"{field}.certificate"),
            placement=DeploymentPlacement(_tuple_strings(placement.get("gpu_uuids"), field=f"{field}.placement.gpu_uuids")),
            host_identity_digest=_string(value.get("host_identity_digest"), field=f"{field}.host_identity_digest"),
        )
    except (TypeError, ValueError) as exc:
        raise QualifiedModelClosureReadError(f"invalid qualified deployment: {field}") from exc


def _route(raw: object, *, field: str) -> ModelEndpointRoute:
    value = _mapping(raw, field=field)
    try:
        return ModelEndpointRoute(
            deployment_id=_string(value.get("deployment_id"), field=f"{field}.deployment_id"),
            deployment_generation=_string(value.get("deployment_generation"), field=f"{field}.deployment_generation"),
            base_url=_string(value.get("base_url"), field=f"{field}.base_url"),
            completion_path=_string(value.get("completion_path", "/v1/chat/completions"), field=f"{field}.completion_path"),
            timeout_s=float(value.get("timeout_s", 120.0)),
        )
    except (TypeError, ValueError) as exc:
        raise QualifiedModelClosureReadError(f"invalid endpoint route: {field}") from exc


def load_qualified_model_deployment_closure(
    path: str | Path,
    *,
    runtime_qualification_store_factory: Callable[[Path], RuntimeQualificationEvidenceStorePort],
) -> QualifiedModelDeploymentClosure:
    """Read one complete qualified deployment closure from an immutable JSON file."""

    closure_path = Path(path).expanduser().resolve(strict=False)
    if not closure_path.is_file():
        raise QualifiedModelClosureReadError(f"qualified model closure is missing: {closure_path}")
    try:
        document = json.loads(closure_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualifiedModelClosureReadError(f"qualified model closure cannot be read: {closure_path}") from exc
    root = _mapping(document, field="root")
    if root.get("schema_version") != _SCHEMA:
        raise QualifiedModelClosureReadError(f"unsupported qualified model closure schema: {root.get('schema_version')!r}")
    role_document = _mapping(root.get("role_manifest"), field="role_manifest")
    assignments_raw = role_document.get("assignments")
    if not isinstance(assignments_raw, list):
        raise QualifiedModelClosureReadError("closure role_manifest.assignments must be a list")
    try:
        role_manifest = RoleModelManifest(
            tuple(
                RoleModelAssignment(
                    role=_string(_mapping(item, field="role assignment").get("role"), field="role"),
                    deployment_id=_string(_mapping(item, field="role assignment").get("deployment_id"), field="deployment_id"),
                )
                for item in assignments_raw
            )
        )
        deployments = tuple(
            _deployment(item, field=f"deployments[{index}]")
            for index, item in enumerate(root.get("deployments", []))
        )
        routes = tuple(
            _route(item, field=f"routes[{index}]")
            for index, item in enumerate(root.get("routes", []))
        )
    except (TypeError, ValueError) as exc:
        raise QualifiedModelClosureReadError("invalid qualified model closure topology") from exc
    runtime_root_raw = root.get("runtime_qualification_root")
    runtime_root_value = _string(runtime_root_raw, field="runtime_qualification_root")
    runtime_root = Path(runtime_root_value)
    if not runtime_root.is_absolute():
        runtime_root = (closure_path.parent / runtime_root).resolve(strict=False)
    runtime_store = runtime_qualification_store_factory(runtime_root)
    if not callable(getattr(runtime_store, "load", None)) or not callable(
        getattr(runtime_store, "publish", None)
    ):
        raise QualifiedModelClosureReadError(
            "runtime qualification store factory returned an invalid port"
        )
    runtime_manifest_digest = _string(root.get("runtime_manifest_digest"), field="runtime_manifest_digest")
    return QualifiedModelDeploymentClosure(
        role_manifest=role_manifest,
        deployments=deployments,
        routes=routes,
        runtime_manifest_digest=runtime_manifest_digest,
        runtime_qualifications=runtime_store,
    )


__all__ = [
    "QualifiedModelClosureReadError",
    "load_qualified_model_deployment_closure",
]
