from __future__ import annotations

from dataclasses import asdict
import json
import sys

from research_platform.operator.api import OperatorHandlerPort
from research_platform.platform.kernel.errors import describe_exception

from .parser import build_parser

_EXPECTED_OPERATOR_ERRORS = (KeyError, ValueError, FileNotFoundError, json.JSONDecodeError)


def _plain(value):
    return asdict(value) if hasattr(value, "__dataclass_fields__") else value


def _emit(value, *, stream=None):
    print(json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, indent=2), file=stream or sys.stdout)


def run_operator_cli(handler: OperatorHandlerPort, argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = handler.handle(args)
    except _EXPECTED_OPERATOR_ERRORS as exc:
        descriptor = describe_exception(exc)
        _emit(
            {
                "ok": False,
                "command": args.command,
                "error_type": descriptor.error_type,
                "error": descriptor.safe_message,
                "error_digest": descriptor.error_digest,
            },
            stream=sys.stderr,
        )
        return 2
    if isinstance(result, int):
        return result
    _emit({"ok": True, "command": args.command, "result": _plain(result)})
    return 0


__all__ = ["run_operator_cli"]
