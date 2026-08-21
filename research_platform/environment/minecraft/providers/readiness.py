from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import socket
import subprocess
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class MinecraftReadinessProbe:
    """One reproducible readiness observation with an actionable cause code."""

    name: str
    ok: bool
    phase: str
    cause_code: str
    detail: str
    command: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class MinecraftReadinessError(RuntimeError):
    """Raised only when a readiness input is malformed, not when a probe fails."""


def parse_node_major(version_text: str) -> int:
    match = re.fullmatch(r"v?(\d+)(?:\.\d+){0,2}", version_text.strip())
    if not match:
        raise MinecraftReadinessError(f"unrecognized Node version: {version_text!r}")
    return int(match.group(1))


def parse_java_major(version_text: str) -> int:
    first = next((line.strip() for line in version_text.splitlines() if line.strip()), "")
    match = re.search(r"\b(?:version\s+)?\"?(\d+)(?:\.|\"|$)", first)
    if not match:
        raise MinecraftReadinessError(f"unrecognized Java version: {first or '<empty>'}")
    return int(match.group(1))


def _run(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return runner(
            list(command),
            cwd=str(cwd) if cwd is not None else None,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None


def probe_node(
    *,
    minimum_major: int = 22,
    command: Sequence[str] = ("node", "--version"),
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> MinecraftReadinessProbe:
    command_tuple = tuple(command)
    result = _run(command_tuple, runner=runner)
    if result is None:
        return MinecraftReadinessProbe(
            "node", False, "runtime", "NODE_NOT_EXECUTABLE", "Node command could not be executed", command_tuple
        )
    text = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        return MinecraftReadinessProbe(
            "node", False, "runtime", "NODE_COMMAND_FAILED", f"rc={result.returncode}: {text}", command_tuple
        )
    try:
        major = parse_node_major(text)
    except MinecraftReadinessError as exc:
        return MinecraftReadinessProbe("node", False, "runtime", "NODE_VERSION_INVALID", str(exc), command_tuple)
    ok = major >= minimum_major
    return MinecraftReadinessProbe(
        "node",
        ok,
        "runtime",
        "OK" if ok else "NODE_VERSION_TOO_OLD",
        f"{text}; required >= v{minimum_major}",
        command_tuple,
    )


def probe_java(
    *,
    minimum_major: int = 21,
    command: Sequence[str] = ("java", "-version"),
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> MinecraftReadinessProbe:
    command_tuple = tuple(command)
    result = _run(command_tuple, runner=runner)
    if result is None:
        return MinecraftReadinessProbe(
            "java", False, "runtime", "JAVA_NOT_EXECUTABLE", "Java command could not be executed", command_tuple
        )
    text = (result.stderr or result.stdout).strip()
    try:
        major = parse_java_major(text)
    except MinecraftReadinessError as exc:
        return MinecraftReadinessProbe("java", False, "runtime", "JAVA_VERSION_INVALID", str(exc), command_tuple)
    ok = result.returncode == 0 and major >= minimum_major
    code = "OK" if ok else "JAVA_VERSION_TOO_OLD" if major < minimum_major else "JAVA_COMMAND_FAILED"
    return MinecraftReadinessProbe(
        "java", ok, "runtime", code, f"{text.splitlines()[0] if text else '<empty>'}; required >= {minimum_major}", command_tuple
    )


def probe_node_package(
    bridge_dir: str | Path,
    *,
    package_name: str,
    expected_version: str | None = None,
    node_command: str = "node",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> MinecraftReadinessProbe:
    script = f"const p=require({package_name!r}+'/package.json');process.stdout.write(String(p.version||''));"
    command = (node_command, "-e", script)
    result = _run(command, cwd=bridge_dir, runner=runner)
    if result is None:
        return MinecraftReadinessProbe(
            package_name, False, "dependencies", "PACKAGE_PROBE_FAILED", "dependency probe could not execute", command
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return MinecraftReadinessProbe(
            package_name,
            False,
            "dependencies",
            "PACKAGE_NOT_RESOLVABLE",
            detail[0] if detail else "module resolution failed",
            command,
        )
    version = result.stdout.strip()
    ok = bool(version) and (expected_version is None or version == expected_version)
    code = "OK" if ok else "PACKAGE_VERSION_MISMATCH" if version else "PACKAGE_VERSION_EMPTY"
    return MinecraftReadinessProbe(
        package_name,
        ok,
        "dependencies",
        code,
        f"resolved {version or '<empty>'}" + (f"; expected {expected_version}" if expected_version else ""),
        command,
    )


def probe_pathfinder(
    bridge_dir: str | Path,
    *,
    expected_version: str = "2.4.5",
    node_command: str = "node",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> MinecraftReadinessProbe:
    result = probe_node_package(
        bridge_dir,
        package_name="mineflayer-pathfinder",
        expected_version=expected_version,
        node_command=node_command,
        runner=runner,
    )
    return MinecraftReadinessProbe(
        "mineflayer_pathfinder", result.ok, result.phase, result.cause_code, result.detail, result.command
    )


def probe_tcp(host: str, port: int, *, timeout_s: float = 2.0) -> MinecraftReadinessProbe:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            pass
    except OSError as exc:
        return MinecraftReadinessProbe(
            "minecraft_server", False, "server", "SERVER_TCP_UNREACHABLE", f"{host}:{port}: {exc}"
        )
    return MinecraftReadinessProbe(
        "minecraft_server", True, "server", "OK", f"{host}:{port} accepted TCP connection"
    )


def minecraft_preflight(
    bridge_dir: str | Path,
    *,
    host: str,
    port: int,
    check_server: bool = True,
    node_command: str = "node",
    java_command: str = "java",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[MinecraftReadinessProbe, ...]:
    results = [
        probe_node(command=(node_command, "--version"), runner=runner),
        probe_java(command=(java_command, "-version"), runner=runner),
        probe_node_package(
            bridge_dir,
            package_name="mineflayer",
            expected_version="4.37.1",
            node_command=node_command,
            runner=runner,
        ),
        probe_pathfinder(bridge_dir, node_command=node_command, runner=runner),
    ]
    if check_server:
        results.append(probe_tcp(host, port))
    return tuple(results)


def report_json(results: Sequence[MinecraftReadinessProbe]) -> str:
    return json.dumps(
        {"ok": all(result.ok for result in results), "results": [result.as_dict() for result in results]},
        ensure_ascii=False,
        indent=2,
    )


__all__ = [
    "MinecraftReadinessError",
    "MinecraftReadinessProbe",
    "minecraft_preflight",
    "parse_java_major",
    "parse_node_major",
    "probe_java",
    "probe_mineflayer",
    "probe_node",
    "probe_node_package",
    "probe_pathfinder",
    "probe_tcp",
    "report_json",
]


def probe_mineflayer(
    bridge_dir: str | Path,
    *,
    expected_version: str = "4.37.1",
    node_command: str = "node",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> MinecraftReadinessProbe:
    return probe_node_package(
        bridge_dir,
        package_name="mineflayer",
        expected_version=expected_version,
        node_command=node_command,
        runner=runner,
    )
