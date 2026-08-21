#!/usr/bin/env python3
"""Manage a persistent operator shell on one environment-configured server.

This is an operator connection helper, not a scientific runtime manager.
Remote tmux owns shell persistence; runtime/server/identity owns SSH identity
and argv construction. No password is accepted by this script or written to
the local binding state.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.runtime.host.composition import compose_local_host
from research_platform.runtime.server.identity.composition import compose_environment_server_identity


_SESSION_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _connection(server_id: str):
    meta = build_in_memory_platform_meta()
    host = compose_local_host(planner=meta.capability_composition)
    identity = compose_environment_server_identity(
        operating_system=host.operating_system,
        host_operating_system_offer=host.operating_system_offer,
        planner=meta.capability_composition,
    )
    return identity.connection_factory.from_environment(server_id)


def _session_name(value: str) -> str:
    if _SESSION_RE.fullmatch(value) is None:
        raise ValueError("session must match [A-Za-z0-9_.-]{1,64}")
    return value


def _remote_tmux(args, *, action: str) -> str:
    tmux = shlex.quote(args.tmux)
    session = _session_name(args.session)
    session_arg = shlex.quote(session)
    session_target = shlex.quote(f"={session}")
    pane_target = shlex.quote(f"={session}:0.0")
    if action == "ensure":
        if not posixpath.isabs(args.cwd):
            raise ValueError("remote cwd must be an absolute POSIX path")
        return (
            f"{tmux} has-session -t {session_target} 2>/dev/null"
            f" || {tmux} new-session -d -s {session_arg} -c {shlex.quote(args.cwd)}"
        )
    if action == "status":
        return f"{tmux} display-message -p -t {pane_target} '#{{session_name}}\\t#{{pane_pid}}\\t#{{pane_dead}}\\t#{{pane_current_path}}'"
    if action == "attach":
        return f"{tmux} attach-session -t {session_target}"
    raise ValueError(f"unsupported server session action: {action}")


def _payload(result) -> dict[str, object]:
    return {
        "server_id": result.server_id,
        "command": result.command,
        "return_code": result.return_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "succeeded": result.succeeded,
    }


def _emit(payload: dict[str, object]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def _ensure(args) -> int:
    connection = _connection(args.server_id)
    result = connection.execute(_remote_tmux(args, action="ensure"), interactive=args.interactive)
    payload = _payload(result)
    payload["session"] = args.session
    payload["cwd"] = args.cwd
    payload["persistent"] = result.succeeded
    payload["attach_argv"] = list(connection.interactive_argv(_remote_tmux(args, action="attach")))
    return _emit(payload)


def _status(args) -> int:
    connection = _connection(args.server_id)
    result = connection.execute(_remote_tmux(args, action="status"), interactive=args.interactive)
    return _emit(_payload(result))


def _attach(args) -> int:
    connection = _connection(args.server_id)
    argv = connection.interactive_argv(_remote_tmux(args, action="attach"))
    completed = subprocess.run(argv, check=False)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure, inspect or attach to a persistent remote tmux shell")
    sub = parser.add_subparsers(dest="action", required=True)

    def common(command):
        command.add_argument("server_id", help="logical id from RP_SERVER_<ID>_*")
        command.add_argument("--session", default="research-platform-shell")
        command.add_argument("--tmux", default="tmux", help="remote tmux executable")
        command.add_argument("--interactive", action="store_true", help="allow OpenSSH to prompt for authentication")

    ensure = sub.add_parser("ensure")
    common(ensure)
    ensure.add_argument("--cwd", default="/data/research-platform/agent-research-platform-system")
    ensure.set_defaults(func=_ensure)

    status = sub.add_parser("status")
    common(status)
    status.set_defaults(func=_status)

    attach = sub.add_parser("attach")
    common(attach)
    attach.set_defaults(func=_attach)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(
            json.dumps(
                {"server_id": getattr(args, "server_id", None), "error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
