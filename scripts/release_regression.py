from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import platform
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from research_platform.governance.release.runtime.regression_state import (
    REGRESSION_STATE_SCHEMA_VERSION,
    ReleaseRegressionShardResult,
    ReleaseRegressionState,
    default_regression_state_path,
    load_regression_state,
    shard_identity_digest,
    test_inventory_digest,
    write_regression_state,
)
from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.runtime.host.composition import compose_local_host


_COLLECT_RE = re.compile(r"(?P<count>\d+) tests? collected")
_RESULT_RE = re.compile(
    r"(?P<passed>\d+) passed(?:, (?P<skipped>\d+) skipped)?"
)
_PLATFORM_META = build_in_memory_platform_meta()
_HOST_OS = compose_local_host(
    planner=_PLATFORM_META.capability_composition,
).operating_system


class ReleaseRegressionFailure(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseRegressionResult:
    collected: int
    passed: int
    skipped: int
    shard_count: int
    test_inventory_sha256: str
    runtime_sha256: str


def _signal_process_group(pgid: int, sig: signal.Signals) -> bool:
    if _HOST_OS.is_windows:
        if sig is signal.SIGTERM:
            try:
                os.kill(pgid, signal.CTRL_BREAK_EVENT)
                return True
            except (AttributeError, OSError):
                # Windows has no POSIX process-group signal. The force phase
                # below still terminates the entire tree with taskkill.
                return _process_group_exists(pgid)
        result = subprocess.run(
            ["taskkill", "/PID", str(pgid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    return True


def _process_group_exists(pgid: int) -> bool:
    if _HOST_OS.is_windows:
        try:
            os.kill(pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _force_process_group(pgid: int) -> bool:
    if _HOST_OS.is_windows:
        result = subprocess.run(
            ["taskkill", "/PID", str(pgid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    return _signal_process_group(pgid, signal.SIGKILL)


def _reap_process_group(pgid: int, *, grace_seconds: float = 0.25) -> None:
    """Best-effort cleanup for descendants left after the pytest leader exits.

    Every pytest shard is started in its own session, so its process-group id is private to
    that shard.  A crash/restart test may intentionally spawn subprocesses; none are allowed
    to survive the shard boundary because they would contaminate later shards or the release
    runner itself.
    """

    if not _signal_process_group(pgid, signal.SIGTERM):
        return
    deadline = time.monotonic() + max(0.0, grace_seconds)
    while time.monotonic() < deadline:
        if not _process_group_exists(pgid):
            return
        time.sleep(0.01)
    _force_process_group(pgid)
    if not _HOST_OS.is_windows:
        # The shard leader is also the process-group leader and therefore the
        # direct child of this runner.  Reap it explicitly after the force
        # phase; otherwise a killed fallback/pytest leader can remain visible
        # as a running process or an unreaped zombie.
        try:
            os.waitpid(pgid, os.WNOHANG)
        except (ChildProcessError, OSError):
            pass


@contextmanager
def _child_process_group_signal_guard(pgid: int):
    """Reap the active shard before propagating an external runner interruption."""

    previous: dict[signal.Signals, object] = {}

    def handle(signum: int, _frame) -> None:
        _reap_process_group(pgid)
        raise SystemExit(128 + int(signum))

    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.getsignal(sig)
        signal.signal(sig, handle)
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _run_pytest(root: Path, args: list[str], *, timeout_seconds: float = 180.0, echo_success: bool = False) -> str:
    # Do not use stdout=PIPE here. Several crash/restart tests intentionally spawn real
    # child processes; inherited pipe FDs can keep communicate() waiting after pytest exits.
    # A regular file decouples child-process FD lifetime from regression-runner completion.
    # start_new_session gives each shard a private process group that can be reaped as one
    # unit even if pytest itself exits before a descendant.
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".pytest.log") as log:
        worker = Path(__file__).resolve().with_name("release_pytest_worker.py")
        if not worker.is_file():
            raise ReleaseRegressionFailure("release pytest worker is missing")
        process = subprocess.Popen(
            [sys.executable, str(worker), *args],
            cwd=root,
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=not _HOST_OS.is_windows,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if _HOST_OS.is_windows
                else 0
            ),
        )
        pgid = process.pid
        try:
            with _child_process_group_signal_guard(pgid):
                returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            _reap_process_group(pgid)
            leader_reaped = True
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                # Never perform an unbounded wait here. A process in uninterruptible kernel
                # sleep cannot be synchronously reaped even after SIGKILL; release verification
                # must fail closed with a precise shard identity rather than hang forever.
                process.kill()
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    leader_reaped = False
            log.flush()
            log.seek(0)
            output = log.read()
            print(output, end="")
            suffix = "" if leader_reaped else f"; pytest leader pid={process.pid} remained unreaped after SIGKILL"
            raise ReleaseRegressionFailure(
                f"pytest timed out after {timeout_seconds:g}s: {' '.join(args)}{suffix}"
            ) from exc
        else:
            # A successful pytest leader must not leave crash-test descendants behind.  The
            # process group is private to this shard, so terminating residual members cannot
            # affect the caller or another shard.
            _reap_process_group(pgid)

        log.flush()
        log.seek(0)
        output = log.read()
    if returncode != 0:
        print(output, end="")
        raise ReleaseRegressionFailure(
            f"pytest failed with exit code {returncode}"
        )
    if echo_success:
        print(output, end="")
    return output


def _parse_collected(output: str) -> int:
    matches = list(_COLLECT_RE.finditer(output))
    if not matches:
        raise ReleaseRegressionFailure("unable to parse pytest collection count")
    return int(matches[-1].group("count"))


def _parse_result(output: str) -> tuple[int, int]:
    matches = list(_RESULT_RE.finditer(output))
    if not matches:
        raise ReleaseRegressionFailure("unable to parse pytest shard result")
    match = matches[-1]
    return int(match.group("passed")), int(match.group("skipped") or 0)


def _regression_runtime_digest() -> str:
    try:
        import pytest
        pytest_version = pytest.__version__
    except ModuleNotFoundError:
        # The release runner records the missing runner in its identity and
        # fails the real regression inventory closed.  A tiny fixture fallback
        # in the worker exists only for process-reaping tests.
        pytest_version = "unavailable"
    payload = {
        "python_version": sys.version,
        "python_implementation": sys.implementation.name,
        "python_cache_tag": sys.implementation.cache_tag,
        "pytest_version": pytest_version,
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine(),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run_release_regression(
    root: Path,
    *,
    source_manifest_digest: str,
    shard_size: int = 32,
    state_path: Path | None = None,
) -> ReleaseRegressionResult:
    """Run or resume the complete test inventory in isolated deterministic shards.

    Successful shard results are durably checkpointed outside the source tree and are reusable
    only when source manifest, test inventory, Python/pytest/platform runtime and shard size all
    match exactly.  An interrupted CI/release command therefore resumes without mixing evidence
    from different source or execution environments.
    """

    root = Path(root).resolve()
    if shard_size <= 0:
        raise ValueError("shard_size must be positive")
    if not source_manifest_digest:
        raise ValueError("source_manifest_digest is required")

    collected_output = _run_pytest(root, ["--collect-only", "-q"])
    collected = _parse_collected(collected_output)
    print(f"RELEASE_TEST_COLLECTION_PASS collected={collected}", flush=True)

    files = tuple(sorted((root / "tests").glob("test_*.py")))
    if not files:
        raise ReleaseRegressionFailure("release regression has no test files")
    relative_files = tuple(path.relative_to(root).as_posix() for path in files)
    inventory_sha256 = test_inventory_digest(relative_files)
    runtime_sha256 = _regression_runtime_digest()
    resolved_state_path = Path(state_path) if state_path is not None else default_regression_state_path(root)

    try:
        state = load_regression_state(resolved_state_path)
    except ValueError as exc:
        raise ReleaseRegressionFailure("release regression durable state is corrupt") from exc

    if state is None or not state.matches(
        source_manifest_digest=source_manifest_digest,
        test_inventory_sha256=inventory_sha256,
        runtime_sha256=runtime_sha256,
        tests_collected=collected,
        shard_size=shard_size,
    ):
        state = ReleaseRegressionState(
            schema_version=REGRESSION_STATE_SCHEMA_VERSION,
            source_manifest_digest=source_manifest_digest,
            test_inventory_sha256=inventory_sha256,
            runtime_sha256=runtime_sha256,
            tests_collected=collected,
            shard_size=shard_size,
            completed_shards=(),
        )
        write_regression_state(resolved_state_path, state)
        print("RELEASE_TEST_STATE_INITIALIZED", flush=True)
    else:
        print(
            f"RELEASE_TEST_STATE_RESUME completed_shards={len(state.completed_shards)}",
            flush=True,
        )

    passed = 0
    skipped = 0
    shard_count = 0
    for offset in range(0, len(files), shard_size):
        shard = files[offset : offset + shard_size]
        relative = tuple(path.relative_to(root).as_posix() for path in shard)
        shard_index = offset // shard_size + 1
        identity = shard_identity_digest(relative)
        cached = state.result_for(shard_index, identity)
        if cached is not None:
            print(
                f"RELEASE_TEST_SHARD_RESUME {shard_index} "
                f"passed={cached.passed} skipped={cached.skipped}",
                flush=True,
            )
            passed += cached.passed
            skipped += cached.skipped
            shard_count += 1
            continue

        print(
            f"RELEASE_TEST_SHARD_START {shard_index} "
            f"files={relative[0]}..{relative[-1]}",
            flush=True,
        )
        output = _run_pytest(root, ["-q", *relative])
        shard_passed, shard_skipped = _parse_result(output)
        result = ReleaseRegressionShardResult(
            shard_index=shard_index,
            shard_identity_sha256=identity,
            first_test_file=relative[0],
            last_test_file=relative[-1],
            passed=shard_passed,
            skipped=shard_skipped,
        )
        state = state.with_result(result)
        write_regression_state(resolved_state_path, state)
        print(
            f"RELEASE_TEST_SHARD_PASS {shard_index} "
            f"passed={shard_passed} skipped={shard_skipped}",
            flush=True,
        )
        passed += shard_passed
        skipped += shard_skipped
        shard_count += 1

    if passed + skipped != collected:
        raise ReleaseRegressionFailure(
            "release regression inventory mismatch: "
            f"collected={collected} passed={passed} skipped={skipped}"
        )
    return ReleaseRegressionResult(
        collected=collected,
        passed=passed,
        skipped=skipped,
        shard_count=shard_count,
        test_inventory_sha256=inventory_sha256,
        runtime_sha256=runtime_sha256,
    )


__all__ = [
    "ReleaseRegressionFailure",
    "ReleaseRegressionResult",
    "run_release_regression",
]
