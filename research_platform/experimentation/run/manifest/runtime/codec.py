from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from ..api import CompositionPlanReference, RunLaunchManifest


class RunLaunchManifestDecodeError(ValueError):
    """A launch-manifest document violates the frozen run contract."""


def encode_run_launch_manifest(manifest: RunLaunchManifest) -> bytes:
    return json.dumps(
        asdict(manifest),
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8") + b"\n"


def decode_run_launch_manifest(raw: bytes) -> RunLaunchManifest:
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise TypeError("run launch manifest must be an object")
        expected = {
            "release_digest",
            "prompt_generation_digest",
            "prompt_promotion_digest",
            "role_model_manifest_digest",
            "qualified_deployment_digests",
            "target_host_identity_digest",
            "participant_implementation_inventory_digest",
            "participant_runtime_inventory_digest",
            "participant_binding_manifest_digest",
            "experiment_spec_digest",
            "command_argv",
            "launcher_binary_sha256",
            "command_environment_digest",
            "config_digests",
            "seed_identity",
            "composition_plans",
        }
        if set(data) != expected:
            raise ValueError("run launch manifest fields are not exact")
        plans_raw = data["composition_plans"]
        config_raw = data["config_digests"]
        if not isinstance(plans_raw, list) or not isinstance(config_raw, list):
            raise TypeError("run launch manifest nested fields must be lists")

        def string_list(value: object, field: str) -> tuple[str, ...]:
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise TypeError(f"run launch manifest {field} must be a list of strings")
            return tuple(value)

        plan_fields = {"composition_id", "owner_key", "scope_key", "plan_digest"}
        plans = []
        for row in plans_raw:
            if not isinstance(row, dict) or set(row) != plan_fields:
                raise TypeError("run launch manifest composition plan is not exact")
            plans.append(CompositionPlanReference(**row))
        config: list[tuple[str, str]] = []
        for row in config_raw:
            if (
                not isinstance(row, list)
                or len(row) != 2
                or any(not isinstance(item, str) for item in row)
            ):
                raise TypeError("run launch manifest config digest must be a pair of strings")
            config.append((row[0], row[1]))
        return RunLaunchManifest(
            release_digest=str(data["release_digest"]),
            prompt_generation_digest=str(data["prompt_generation_digest"]),
            prompt_promotion_digest=str(data["prompt_promotion_digest"]),
            role_model_manifest_digest=str(data["role_model_manifest_digest"]),
            qualified_deployment_digests=string_list(
                data["qualified_deployment_digests"], "qualified_deployment_digests"
            ),
            target_host_identity_digest=str(data["target_host_identity_digest"]),
            participant_implementation_inventory_digest=str(data["participant_implementation_inventory_digest"]),
            participant_runtime_inventory_digest=str(data["participant_runtime_inventory_digest"]),
            participant_binding_manifest_digest=str(data["participant_binding_manifest_digest"]),
            experiment_spec_digest=str(data["experiment_spec_digest"]),
            command_argv=string_list(data["command_argv"], "command_argv"),
            launcher_binary_sha256=str(data["launcher_binary_sha256"]),
            command_environment_digest=str(data["command_environment_digest"]),
            config_digests=tuple(config),
            seed_identity=str(data["seed_identity"]),
            composition_plans=tuple(plans),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RunLaunchManifestDecodeError(
            "run launch manifest violates the frozen run contract"
        ) from exc


def load_run_launch_manifest(path: str | Path) -> RunLaunchManifest:
    manifest_path = Path(path).expanduser().resolve()
    if not manifest_path.is_file():
        raise RunLaunchManifestDecodeError(
            f"run launch manifest is not a regular file: {manifest_path}"
        )
    try:
        return decode_run_launch_manifest(manifest_path.read_bytes())
    except OSError as exc:
        raise RunLaunchManifestDecodeError(
            f"run launch manifest cannot be read: {manifest_path}"
        ) from exc


__all__ = [
    "RunLaunchManifestDecodeError",
    "decode_run_launch_manifest",
    "encode_run_launch_manifest",
    "load_run_launch_manifest",
]
