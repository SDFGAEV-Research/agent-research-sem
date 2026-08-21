#!/usr/bin/env python3
"""Operate one environment-configured persistent server operator session.

The script is deliberately thin: server identity, remote runtime paths,
tmux transport attestation, durable bindings and reconciliation belong to
their respective platform ports. It does not contain a second server registry
or a remote shell command builder.
"""

from __future__ import annotations

import argparse
import json
import subprocess
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
from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.runtime.host.composition import compose_local_host
from research_platform.runtime.server.identity.composition import compose_environment_server_identity
from research_platform.runtime.server.lifecycle.api import ServerRemoteProfile
from research_platform.runtime.server.lifecycle.providers import SSHRemoteTmuxSessionControl
from research_platform.runtime.session.api import PersistentSessionSpec
from research_platform.runtime.session.runtime import (
    BoundPersistentSessionStatusProbe,
    DirectoryPersistentSessionBindingStore,
    PersistentSessionManager,
)


def _connection(server_id: str):
    meta = build_in_memory_platform_meta()
    host = compose_local_host(planner=meta.capability_composition)
    identity = compose_environment_server_identity(
        operating_system=host.operating_system,
        host_operating_system_offer=host.operating_system_offer,
        planner=meta.capability_composition,
    )
    return identity.connection_factory.from_environment(server_id)


def _control(connection, profile: ServerRemoteProfile, *, interactive: bool):
    return SSHRemoteTmuxSessionControl(
        connection,
        tmux_executable=profile.tmux_executable,
        binary_identity_digest=profile.tmux_binary_sha256,
        server_label=profile.tmux_server_label,
        config_file=profile.tmux_config_file,
        socket_directory=profile.tmux_socket_directory,
        remote_env_executable=profile.remote_env_executable,
        sha256sum_executable=profile.sha256sum_executable,
        session_environment=profile.session_environment,
        interactive=interactive,
    )


def _spec(profile: ServerRemoteProfile, session_name: str) -> PersistentSessionSpec:
    command_argv = (profile.operator_shell, "-l")
    return PersistentSessionSpec(
        session_name=session_name,
        command_argv=command_argv,
        cwd=profile.operator_cwd,
        control_id=f"operator-shell:{profile.server_id}",
        runtime_manifest_digest=canonical_digest(
            {
                "server_id": profile.server_id,
                "platform_root": profile.platform_root,
                "operator_cwd": profile.operator_cwd,
                "operator_shell": profile.operator_shell,
                "remote_path": profile.remote_path,
                "session_environment": profile.session_environment,
            }
        ),
        process_environment=profile.session_environment,
    )


def _manager(server_id: str, *, interactive: bool, session_override: str | None):
    profile = ServerRemoteProfile.from_environment(server_id)
    session_name = session_override or profile.session_name
    connection = _connection(server_id)
    control = _control(connection, profile, interactive=interactive)
    profile.local_binding_root.mkdir(parents=True, exist_ok=True)
    bindings = DirectoryPersistentSessionBindingStore(profile.local_binding_root)
    manager = PersistentSessionManager(control, bindings)
    return profile, control, manager, _spec(profile, session_name), bindings


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
    profile, _control, manager, spec, _bindings = _manager(
        args.server_id, interactive=args.interactive, session_override=args.session
    )
    report = manager.ensure(spec)
    return _emit(
        {
            "server_id": profile.server_id,
            "session": spec.session_name,
            "persistent": True,
            "reused": report.reused,
            "spec_digest": report.spec_digest,
            "transport_identity_digest": manager.transport_identity_digest,
            "transport_identity_verified": manager.transport_identity_verified,
            "controller_pid": report.snapshot.controller_pid,
            "cwd": spec.cwd,
            "attach_argv": list(report.attach_argv),
            "evidence_refs": list(report.evidence_refs),
        }
    )


def _status(args) -> int:
    profile, control, _manager, spec, bindings = _manager(
        args.server_id, interactive=args.interactive, session_override=args.session
    )
    observation = BoundPersistentSessionStatusProbe(control, bindings, spec.session_name).observe()
    payload = {"server_id": profile.server_id}
    payload.update(_observation_payload(observation))
    return _emit(payload)


def _attach(args) -> int:
    profile, control, _manager, spec, _bindings = _manager(
        args.server_id, interactive=True, session_override=args.session
    )
    completed = subprocess.run(control.attach_argv(spec.session_name), check=False)
    return completed.returncode


def _terminate(args) -> int:
    profile, _control, manager, spec, _bindings = _manager(
        args.server_id, interactive=args.interactive, session_override=args.session
    )
    evidence_refs = manager.terminate(spec)
    return _emit(
        {
            "server_id": profile.server_id,
            "session": spec.session_name,
            "terminated": True,
            "evidence_refs": list(evidence_refs),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a persistent remote operator session")
    sub = parser.add_subparsers(dest="action", required=True)

    def common(command):
        command.add_argument("server_id", help="logical id from RP_SERVER_<ID>_*")
        command.add_argument("--session", help="optional override of the profile session name")
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
