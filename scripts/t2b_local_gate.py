#!/usr/bin/env python3
"""Canonical one-process, one-world T2B live gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.environment.minecraft.api import MinecraftServerSpec
from research_platform.environment.minecraft.providers.readiness import probe_java, probe_node, probe_node_package
from research_platform.environment.minecraft.providers.server_files import prepare_server_files, sha256_file
from research_platform.platform.kernel import canonical_digest


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _wait_tcp(host: str, port: int, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"Minecraft TCP readiness timed out: {host}:{port}")


def _preflight(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    probes = [probe_java(command=(args.java, "-version")), probe_node(command=(args.node, "--version"))]
    for package, expected in (("mineflayer", "4.37.1"), ("mineflayer-pathfinder", "2.4.5"), ("mineflayer-pvp", "1.3.2"), ("vec3", "0.1.8")):
        probes.append(probe_node_package(args.bridge_dir, package_name=package, expected_version=expected, node_command=args.node))
    if not args.server_jar.is_file():
        blockers = [f"SERVER_JAR_MISSING:{args.server_jar}"]
    else:
        blockers = []
    blockers.extend(f"{probe.name}:{probe.cause_code}:{probe.detail}" for probe in probes if not probe.ok)
    return {"probes": [probe.as_dict() for probe in probes], "server_jar": str(args.server_jar), "server_jar_sha256": sha256_file(args.server_jar) if args.server_jar.is_file() else None}, blockers


def run(args: argparse.Namespace) -> int:
    args.server_jar = args.server_jar.resolve()
    args.bridge_dir = args.bridge_dir.resolve()
    workdir = args.workdir.resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    preflight, blockers = _preflight(args)
    if blockers:
        _write(workdir / "T2B_GATE_RESULT.json", {
            "schema": "t2b-gate.v2",
            "status": "T2B_GATE_BLOCKED",
            "failure_class": "ENVIRONMENT",
            "same_server_process_for_both_seeds": False,
            "blockers": blockers,
            "preflight": preflight,
        })
        return 2
    spec = MinecraftServerSpec(
        jar_path=str(args.server_jar), workdir=str(workdir), java_executable=args.java,
        host=args.host, port=args.port, level_name=args.level_name, level_seed=args.level_seed,
    )
    process: subprocess.Popen[str] | None = None
    log_handle = None
    server_identity: dict[str, Any] | None = None
    run_rows: list[dict[str, Any]] = []
    failure: str | None = None
    try:
        prepare_server_files(spec, accept_eula=True)
        log_handle = (workdir / "server.log").open("a", encoding="utf-8")
        process = subprocess.Popen(list(spec.command()), cwd=spec.workdir, stdin=subprocess.PIPE, stdout=log_handle, stderr=subprocess.STDOUT, text=True)
        _wait_tcp(spec.host, spec.port, args.timeout_s)
        level_dir = workdir / spec.level_name
        deadline = time.monotonic() + args.timeout_s
        while not level_dir.is_dir() and time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Minecraft server exited before world creation: {process.returncode}")
            time.sleep(0.25)
        if not level_dir.is_dir() or not (level_dir / "level.dat").is_file():
            raise RuntimeError("persistent world level.dat was not created by the real server")
        server_identity = {
            "pid": process.pid,
            "jar_sha256": sha256_file(args.server_jar),
            "workdir": str(workdir),
            "level_name": spec.level_name,
            "level_dir": str(level_dir),
            "port": spec.port,
        }
        for seed in ("C", "X"):
            seed_dir = workdir / f"seed-{seed}"
            command = [sys.executable, str(ROOT / "scripts" / "t2_live_smoke.py"), "--host", spec.host, "--port", str(spec.port), "--bridge-dir", str(args.bridge_dir), "--seed", seed, "--auth", args.auth, "--version", args.version, "--node", args.node, "--timeout-s", str(args.timeout_s), "--output", str(seed_dir)]
            completed = subprocess.run(command, cwd=str(ROOT), check=False, capture_output=True, text=True)
            result_path = seed_dir / "T2B_SEED_RESULT.json"
            result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {"status": "FAILED", "error": completed.stderr[-2000:]}
            run_rows.append({"seed": seed, "returncode": completed.returncode, "result": result})
            if process.poll() is not None or process.pid != server_identity["pid"]:
                raise RuntimeError("server process identity changed between Seed-C and Seed-X")
            if result.get("status") != "PASS":
                raise RuntimeError(f"Seed-{seed} live smoke failed")
        if not (workdir / spec.level_name / "level.dat").is_file():
            raise RuntimeError("persistent world level.dat disappeared before gate completion")
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        if process is not None and process.poll() is None:
            try:
                if process.stdin is not None:
                    process.stdin.write("save-all\nstop\n")
                    process.stdin.flush()
                process.wait(timeout=30)
            except Exception:
                process.kill()
                process.wait(timeout=10)
        if log_handle is not None:
            log_handle.close()
    passed = failure is None and len(run_rows) == 2 and all(row["result"].get("status") == "PASS" for row in run_rows)
    result = {
        "schema": "t2b-gate.v2",
        "status": "T2B_GATE_PASS" if passed else "T2B_GATE_FAILED",
        "failure_class": "NONE" if passed else "LIVE_RUNTIME",
        "same_server_process_for_both_seeds": passed,
        "server_identity": server_identity,
        "runs": run_rows,
        "preflight": preflight,
        "error": failure,
        "world_level_dat_sha256": sha256_file(workdir / args.level_name / "level.dat") if (workdir / args.level_name / "level.dat").is_file() else None,
    }
    result["gate_digest"] = canonical_digest(result)
    _write(workdir / "T2B_GATE_RESULT.json", result)
    return 0 if passed else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-jar", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--bridge-dir", type=Path, default=ROOT / "research_platform/environment/minecraft/providers/assets/mineflayer_bridge")
    parser.add_argument("--java", default="java")
    parser.add_argument("--node", default="node")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=25565)
    parser.add_argument("--level-name", default="t2b-persistent-world")
    parser.add_argument("--level-seed", default="SEM_T2B_FIXED_WORLD_V1")
    parser.add_argument("--auth", default="offline")
    parser.add_argument("--version", default="1.21.8")
    parser.add_argument("--timeout-s", type=float, default=180.0)
    args = parser.parse_args(argv)
    if args.timeout_s <= 0:
        parser.error("--timeout-s must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
