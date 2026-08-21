from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.runtime.server.identity.composition import build_environment_server_connection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a managed server from environment configuration")
    parser.add_argument("server_id", help="logical server id; values come from RP_SERVER_<ID>_*")
    parser.add_argument("--interactive", action="store_true", help="allow OpenSSH to prompt on the terminal")
    args = parser.parse_args(argv)
    try:
        connection = build_environment_server_connection(args.server_id)
        report = connection.health(interactive=args.interactive)
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
        "return_code": report.raw.return_code,
        "stderr": report.raw.stderr,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if report.reachable else 1


if __name__ == "__main__":
    raise SystemExit(main())
