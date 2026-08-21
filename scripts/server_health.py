from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

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

from server_common import compose_script_server
from research_platform.runtime.server.health.api import ServerRuntimeHealthSpec
from research_platform.runtime.server.health.composition import compose_ssh_server_health


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a managed server from environment configuration")
    parser.add_argument("server_id", help="logical server id; values come from RP_SERVER_<ID>_*")
    parser.add_argument(
        "--profile-file",
        help="literal KEY=value profile; also configurable via RP_SERVER_PROFILE_FILE",
    )
    parser.add_argument("--interactive", action="store_true", help="allow OpenSSH to prompt on the terminal")
    args = parser.parse_args(argv)
    try:
        _environ, server = compose_script_server(args.server_id, profile_file=args.profile_file)
        connection = server.connection
        profile = server.remote_profile
        report = compose_ssh_server_health().probe(
            connection,
            interactive=args.interactive,
            specification=ServerRuntimeHealthSpec(
                platform_root=profile.platform_root,
                release_root=profile.release_root,
                remote_home=profile.remote_home,
                python_executable=profile.python_executable,
                node_executable=profile.node_executable,
                java_executable=profile.java_executable,
                platform_management_executable=profile.platform_management_executable,
                tmux_executable=profile.tmux_executable,
                sha256sum_executable=profile.sha256sum_executable,
                tmux_binary_sha256=profile.tmux_binary_sha256,
            ),
        )
    except Exception as exc:
        print(json.dumps({"server_id": args.server_id, "error_type": type(exc).__name__, "error": str(exc)}))
        return 2
    payload = {
        "server_id": report.server_id,
        "reachable": report.reachable,
        "host_name": report.host_name,
        "python_version": report.python_version,
        "git_version": report.git_version,
        "tmux_version": report.tmux_version,
        "platform_ready": report.platform_ready,
        "checks": dict(report.checks),
        "issues": list(report.issues),
        "profile_digest": server.profile_digest,
        "operation_log": str(server.operation_journal.path),
        "return_code": report.raw.return_code,
        "failure_kind": report.raw.failure_kind.value,
        "duration_seconds": report.raw.duration_seconds,
        "stderr": report.raw.stderr,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if report.platform_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
