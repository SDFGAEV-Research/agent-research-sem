#!/usr/bin/env python3
"""Run one real Mineflayer smoke against an already-running Minecraft server.

This script never starts or resets a server.  The outer T2B gate owns that
lifecycle and invokes this script once for Seed-C and once for Seed-X.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.environment.minecraft.api import (
    MinecraftAgentSpec,
    MinecraftBridgeSpec,
    MinecraftEndpointSpec,
)
from research_platform.environment.minecraft.providers.jsonl_bridge import JsonlMinecraftBridge
from research_platform.platform.composition.concurrency import build_execution_concurrency_runtime
from research_platform.runtime.host.providers import LocalOperatingSystemRoute
from research_platform.platform.kernel import canonical_digest


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    mem_path = output / "J_mem.jsonl"
    audit_path = output / "J_audit.jsonl"
    records: list[dict[str, Any]] = []
    bridge: JsonlMinecraftBridge | None = None
    concurrency_runtime = build_execution_concurrency_runtime()
    bridge_group = concurrency_runtime.open_task_group(f"t2-live-smoke:{args.seed}")
    try:
        bridge = JsonlMinecraftBridge(
            endpoint=MinecraftEndpointSpec(args.host, args.port),
            spec=MinecraftBridgeSpec(
                command=(args.node, str(args.bridge_dir / "bridge.js")),
                cwd=str(args.bridge_dir),
                stderr_log_path=str(output / "bridge.stderr.log"),
                connect_timeout_s=args.timeout_s,
                command_timeout_s=args.timeout_s,
            ),
            agent=MinecraftAgentSpec(
                username=f"ResearchBot{args.seed}",
                auth=args.auth,
                version=args.version,
            ),
            operating_system=LocalOperatingSystemRoute(),
            task_group=bridge_group,
        )
        bridge.start()
        task = bridge.command(
            "task_event",
            {
                "task_id": f"t2b-{args.seed.lower()}-grounding",
                "task": "Observe the current grounded Minecraft world.",
                "goal": "Observe the current grounded Minecraft world.",
                "task_lineage": f"t2b-seed-{args.seed}",
                "context": {"seed": args.seed, "mode": "architecture_blind_smoke"},
                "anchors": [f"t2b:{args.seed}:task"],
            },
            timeout_s=args.timeout_s,
        )
        snapshot = bridge.command("snapshot", {}, timeout_s=args.timeout_s)
        wait = bridge.command("wait", {"ms": 250}, timeout_s=args.timeout_s)
        events = tuple(task.events) + tuple(snapshot.events) + tuple(wait.events)
        for event in events:
            if event.kind not in {"self_snapshot", "entity_observation", "action_result", "task_event"}:
                continue
            seq = len(records) + 1
            source_ref = f"j_mem:{args.seed}:{seq}"
            record = {
                "record_id": source_ref,
                "channel": "J_mem",
                "source_refs": [source_ref],
                "seed": args.seed,
                "event_kind": event.kind,
                "payload": dict(event.payload),
            }
            records.append(record)
        if not records:
            raise RuntimeError("T2B smoke produced no grounded observation events")
        mem_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records), encoding="utf-8")
        audit_path.write_text("", encoding="utf-8")
        materialized_refs = tuple(row["source_refs"][0] for row in records[:2])
        known_refs = {row["record_id"] for row in records}
        if not materialized_refs or any(ref not in known_refs or not ref.startswith("j_mem:") for ref in materialized_refs):
            raise RuntimeError("T2B materialization/source_refs firewall failed")
        result = {
            "schema": "t2b-live-smoke.v2",
            "status": "PASS",
            "seed": args.seed,
            "host": args.host,
            "port": args.port,
            "bridge_process_id": bridge.process_id,
            "spawned": True,
            "grounded_record_count": len(records),
            "materialized_source_refs": list(materialized_refs),
            "j_mem_path": mem_path.name,
            "j_audit_path": audit_path.name,
            "audit_records_materialized": 0,
            "digest": canonical_digest({"seed": args.seed, "records": records}),
        }
        _write(output / "T2B_SEED_RESULT.json", result)
        return 0
    except Exception as exc:
        _write(output / "T2B_SEED_RESULT.json", {
            "schema": "t2b-live-smoke.v2",
            "status": "FAILED",
            "seed": args.seed,
            "error": f"{type(exc).__name__}: {exc}",
        })
        return 2
    finally:
        try:
            if bridge is not None:
                bridge.close()
        finally:
            concurrency_runtime.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=25565)
    parser.add_argument("--bridge-dir", type=Path, required=True)
    parser.add_argument("--seed", choices=("C", "X"), required=True)
    parser.add_argument("--auth", default="offline")
    parser.add_argument("--version", default="1.21.8")
    parser.add_argument("--node", default="node")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.timeout_s <= 0:
        parser.error("--timeout-s must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
