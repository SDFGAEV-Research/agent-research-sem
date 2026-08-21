#!/usr/bin/env python3
"""Read and reconcile the controller-local server operation ledger.

This command never retries, mutates the remote host, or guesses an outcome.
An operation with a durable ``started`` record and no ``finished`` record is
reported as effect-uncertain and must be reconciled by its owning lifecycle
before the same mutation is submitted again.
"""

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


def _record_payload(record) -> dict[str, object]:
    finished = record.finished
    return {
        "operation_id": record.operation_id,
        "server_id": record.server_id,
        "kind": record.kind.value,
        "request_digest": record.started.request_digest,
        "profile_digest": record.started.profile_digest,
        "started_at": record.started.started_at,
        "interactive": record.started.interactive,
        "state": record.state.value,
        "effect_uncertain": record.effect_uncertain,
        "finished_at": finished.finished_at if finished is not None else None,
        "return_code": finished.return_code if finished is not None else None,
        "failure_kind": finished.failure_kind if finished is not None else None,
        "error_type": finished.error_type if finished is not None else None,
        "error_digest": finished.error_digest if finished is not None else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect managed server operation evidence")
    parser.add_argument("server_id", help="logical server id; values come from RP_SERVER_<ID>_*")
    parser.add_argument(
        "--profile-file",
        help="literal KEY=value profile; also configurable via RP_SERVER_PROFILE_FILE",
    )
    parser.add_argument("--limit", type=int, default=20, help="number of recent operation records")
    args = parser.parse_args(argv)
    try:
        _environ, server = compose_script_server(args.server_id, profile_file=args.profile_file)
        pending = server.operation_journal.pending_operations()
        recent = server.operation_journal.recent_operations(args.limit)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "server_id": args.server_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    payload = {
        "server_id": server.server_id,
        "profile_digest": server.profile_digest,
        "operation_log": str(server.operation_journal.path),
        "reconciliation_required": bool(pending),
        "pending_operations": [_record_payload(record) for record in pending],
        "recent_operations": [_record_payload(record) for record in recent],
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
