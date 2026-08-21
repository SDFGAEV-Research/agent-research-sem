#!/usr/bin/env python3
"""Operate one environment-configured persistent server operator session.

The script is deliberately thin: server identity, remote runtime paths,
tmux transport attestation, durable bindings and reconciliation belong to
their respective platform ports. It does not contain a second server registry
or a remote shell command builder.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if sys.version_info < (3, 11):
    print(
        json.dumps(
            {
                "error_type": "ControllerPythonVersionError",
                "error": "server management requires controller Python >=3.11",
                "detected": ".".join(str(part) for part in sys.version_info[:3]),
            },
            sort_keys=True,
        )
    )
    raise SystemExit(2)

from research_platform.platform.kernel import canonical_digest
from scripts.server_common import compose_server_from_environment, load_script_environment
from research_platform.runtime.server.lifecycle.api import ServerRemoteProfile
from research_platform.runtime.server.lifecycle.composition import compose_ssh_server_session_control
from research_platform.runtime.session.api import PersistentSessionSpec
from research_platform.runtime.session.runtime import (
    BoundPersistentSessionStatusProbe,
    DirectoryPersistentSessionBindingStore,
    PersistentSessionManager,
)


def _environment(profile_file: str | None) -> Mapping[str, str]:
    return load_script_environment(profile_file)


def _control(connection, profile: ServerRemoteProfile, *, interactive: bool):
    return compose_ssh_server_session_control(
        connection=connection,
        profile=profile,
        interactive=interactive,
    )


def _spec(server, session_name: str) -> PersistentSessionSpec:
    profile: ServerRemoteProfile = server.remote_profile
    command_argv = (profile.operator_shell, *profile.operator_shell_args)
    return PersistentSessionSpec(
        session_name=session_name,
        command_argv=command_argv,
        cwd=profile.operator_cwd,
        control_id=f"operator-shell:{profile.server_id}",
        runtime_manifest_digest=canonical_digest(
            {
                "server_profile_digest": server.profile_digest,
                "server_id": profile.server_id,
                "platform_root": profile.platform_root,
                "operator_cwd": profile.operator_cwd,
                "operator_shell": profile.operator_shell,
                "operator_shell_args": profile.operator_shell_args,
                "remote_path": profile.remote_path,
                "session_environment": profile.session_environment,
            }
        ),
        process_environment=profile.session_environment,
    )


def _manager(
    server_id: str,
    *,
    interactive: bool,
    session_override: str | None,
    environ: Mapping[str, str],
):
    server = compose_server_from_environment(server_id, environ=environ)
    profile = server.remote_profile
    session_name = session_override or profile.session_name
    control = _control(server.connection, profile, interactive=interactive)
    profile.local_binding_root.mkdir(parents=True, exist_ok=True)
    bindings = DirectoryPersistentSessionBindingStore(profile.local_binding_root)
    manager = PersistentSessionManager(control, bindings)
    return server, control, manager, _spec(server, session_name), bindings


def _observation_payload(observation) -> dict[str, object]:
    return {
        "session": observation.session_name,
        "state": observation.state.value,
        "summary": observation.summary,
        "controller_pid": observation.controller_pid,
        "evidence_refs": list(observation.evidence_refs),
        "attach_argv": list(observation.attach_argv),
        "reason_code": observation.reason_code,
    }


def _emit(payload: dict[str, object]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def _ensure(args) -> int:
    server, _control, manager, spec, _bindings = _manager(
        args.server_id,
        interactive=args.interactive,
        session_override=args.session,
        environ=_environment(args.profile_file),
    )
    report = manager.ensure(spec)
    return _emit(
        {
            "server_id": server.server_id,
            "session": spec.session_name,
            "persistent": True,
            "reused": report.reused,
            "spec_digest": report.spec_digest,
            "transport_identity_digest": manager.transport_identity_digest,
            "transport_identity_verified": manager.transport_identity_verified,
            "profile_digest": server.profile_digest,
            "operation_log": str(server.operation_journal.path),
            "controller_pid": report.snapshot.controller_pid,
            "cwd": spec.cwd,
            "attach_argv": list(report.attach_argv),
            "evidence_refs": list(report.evidence_refs),
        }
    )


def _status(args) -> int:
    server, control, session_manager, spec, bindings = _manager(
        args.server_id,
        interactive=args.interactive,
        session_override=args.session,
        environ=_environment(args.profile_file),
    )
    observation = BoundPersistentSessionStatusProbe(
        control,
        bindings,
        spec.session_name,
        expected_spec=spec,
    ).observe()
    payload = {
        "server_id": server.server_id,
        "profile_digest": server.profile_digest,
        "operation_log": str(server.operation_journal.path),
    }
    payload.update(_observation_payload(observation))
    return _emit(payload)


def _attach(args) -> int:
    server, control, session_manager, spec, _bindings = _manager(
        args.server_id,
        interactive=True,
        session_override=args.session,
        environ=_environment(args.profile_file),
    )
    return server.connection.run_interactive(session_manager.attach(spec))


def _terminate(args) -> int:
    server, _control, session_manager, spec, _bindings = _manager(
        args.server_id,
        interactive=args.interactive,
        session_override=args.session,
        environ=_environment(args.profile_file),
    )
    evidence_refs = session_manager.terminate(spec)
    return _emit(
        {
            "server_id": server.server_id,
            "session": spec.session_name,
            "terminated": True,
            "profile_digest": server.profile_digest,
            "operation_log": str(server.operation_journal.path),
            "evidence_refs": list(evidence_refs),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a persistent remote operator session")
    sub = parser.add_subparsers(dest="action", required=True)

    def common(command):
        command.add_argument("server_id", help="logical id from RP_SERVER_<ID>_*")
        command.add_argument("--session", help="optional override of the profile session name")
        command.add_argument(
            "--profile-file",
            help="literal KEY=value profile; also configurable via RP_SERVER_PROFILE_FILE",
        )
        command.add_argument("--interactive", action="store_true", help="allow OpenSSH to prompt for authentication")

    ensure = sub.add_parser("ensure")
    common(ensure)
    ensure.set_defaults(func=_ensure)

    status = sub.add_parser("status")
    common(status)
    status.set_defaults(func=_status)

    attach = sub.add_parser("attach")
    attach.add_argument("server_id", help="logical id from RP_SERVER_<ID>_*")
    attach.add_argument("--session", help="optional override of the profile session name")
    attach.add_argument(
        "--profile-file",
        help="literal KEY=value profile; also configurable via RP_SERVER_PROFILE_FILE",
    )
    attach.set_defaults(func=_attach)

    terminate = sub.add_parser("terminate")
    common(terminate)
    terminate.set_defaults(func=_terminate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "server_id": getattr(args, "server_id", None),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
