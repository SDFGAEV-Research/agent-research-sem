from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
import sys

from research_platform.environment.python.api import EnvironmentCommandResult
from research_platform.platform.composition.model_management import build_local_management_plane
from research_platform.resource.directory.api import DirectoryLayout
from research_platform.platform.kernel.errors import describe_exception
from .management import DISPATCH, ManagementCommandContext, register_all


def _plain(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _emit(value, *, stream=None) -> None:
    print(json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, indent=2), file=stream or sys.stdout)


def _load_context(config_path: Path) -> ManagementCommandContext:
    data = json.loads(config_path.read_text("utf-8"))
    layout = DirectoryLayout(
        **{
            key: Path(value).expanduser().resolve()
            for key, value in data["directories"].items()
        }
    )
    base_environment = tuple(sorted((str(k), str(v)) for k, v in data.get("service_environment", {}).items()))
    source_config = data.get("model_sources", {})
    model_source_environment = tuple(
        sorted((str(key), str(value)) for key, value in data.get("model_source_environment", {}).items())
    )
    storage_pools = {
        str(pool_id): Path(value).expanduser().resolve()
        for pool_id, value in data.get("model_storage_pools", {}).items()
    }
    plane = build_local_management_plane(
        layout,
        base_service_environment=base_environment,
        model_source_environment=model_source_environment,
        huggingface_cli=str(source_config.get("huggingface_cli", "hf")),
        model_storage_pools=storage_pools,
    )
    return ManagementCommandContext(
        plane.scopes,
        plane.directories,
        plane.execution_environments,
        plane.python_environments,
        plane.models,
        plane.deployment_qualification,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research-platform-manage")
    parser.add_argument("--config", required=True, type=Path)
    groups = parser.add_subparsers(dest="group", required=True)
    register_all(groups)
    return parser


def _require_command_success(result):
    """Turn a managed subprocess failure into a failed management command."""

    if isinstance(result, EnvironmentCommandResult) and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(
            f"managed environment command failed with exit code {result.returncode}{suffix}"
        )
    return result


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        context = _load_context(args.config)
        result = _require_command_success(DISPATCH[args.group](args, context))
    except (KeyError, ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        descriptor = describe_exception(exc)
        _emit(
            {
                "ok": False,
                "error_type": descriptor.error_type,
                "error": descriptor.safe_message,
                "error_digest": descriptor.error_digest,
            },
            stream=sys.stderr,
        )
        return 2
    _emit({"ok": True, "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
