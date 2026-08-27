from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import os
import signal
import subprocess
from threading import Lock
from typing import Mapping

from research_platform.platform.concurrency.api import (
    Deadline,
    ExecutionLaneKind,
    ExecutionSpec,
    TaskFailureScope,
    TaskGroupPort,
)

from ..api import ProcessCommandResult, ProcessCommandRunnerPort


@dataclass(slots=True)
class _BoundedPipeCollector:
    limit: int
    captured: bytearray = field(default_factory=bytearray)
    total_bytes: int = 0

    async def drain(self, reader: asyncio.StreamReader | None) -> None:
        if reader is None:
            return
        while True:
            chunk = await reader.read(64 * 1024)
            if not chunk:
                return
            self.total_bytes += len(chunk)
            remaining = self.limit - len(self.captured)
            if remaining > 0:
                self.captured.extend(chunk[:remaining])

    @property
    def value(self) -> bytes:
        return bytes(self.captured)

    @property
    def truncated(self) -> bool:
        return self.total_bytes > len(self.captured)


class AsyncProcessCommandRunner(ProcessCommandRunnerPort):
    """Task-group-owned local command runner with bounded pipe retention.

    Child count is governed by the structured ASYNC_IO lane.  Pipe memory is
    governed independently: stdout/stderr continue to be drained after their
    retention limit is reached so the child cannot deadlock on a full pipe, but
    excess bytes are discarded while exact total-byte accounting is retained.
    """

    def __init__(
        self,
        task_group: TaskGroupPort,
        *,
        cleanup_timeout_seconds: float = 2.0,
        default_output_limit_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        if cleanup_timeout_seconds <= 0:
            raise ValueError("process command cleanup timeout must be positive")
        if default_output_limit_bytes <= 0:
            raise ValueError("process command output limit must be positive")
        self._task_group = task_group
        self._cleanup_timeout_seconds = float(cleanup_timeout_seconds)
        self._default_output_limit_bytes = int(default_output_limit_bytes)
        self._lock = Lock()
        self._sequence = 0

    def _task_id(self, argv: tuple[str, ...]) -> str:
        if not argv or not str(argv[0]).strip():
            raise ValueError("process command argv must be non-empty")
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
        executable = str(argv[0]).rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        return f"process-command:{executable}:{sequence}"

    @staticmethod
    def _signal_process(process: asyncio.subprocess.Process, *, force: bool) -> None:
        if process.returncode is not None:
            return
        if os.name == "posix":
            try:
                os.killpg(
                    int(process.pid),
                    signal.SIGKILL if force else signal.SIGTERM,
                )
            except ProcessLookupError:
                return
            return
        try:
            if force:
                process.kill()
            else:
                process.terminate()
        except ProcessLookupError:
            return

    @staticmethod
    async def _drain_and_wait(
        process: asyncio.subprocess.Process,
        stdout: _BoundedPipeCollector,
        stderr: _BoundedPipeCollector,
    ) -> None:
        await asyncio.gather(
            stdout.drain(process.stdout),
            stderr.drain(process.stderr),
            process.wait(),
        )

    async def _terminate_and_drain(
        self,
        process: asyncio.subprocess.Process,
        stdout: _BoundedPipeCollector,
        stderr: _BoundedPipeCollector,
    ) -> None:
        if process.returncode is not None:
            await self._drain_and_wait(process, stdout, stderr)
            return
        self._signal_process(process, force=False)
        try:
            await asyncio.wait_for(
                self._drain_and_wait(process, stdout, stderr),
                timeout=self._cleanup_timeout_seconds,
            )
            return
        except asyncio.TimeoutError:
            pass
        self._signal_process(process, force=True)
        await asyncio.wait_for(
            self._drain_and_wait(process, stdout, stderr),
            timeout=self._cleanup_timeout_seconds,
        )

    @staticmethod
    def _result(
        process: asyncio.subprocess.Process,
        stdout: _BoundedPipeCollector,
        stderr: _BoundedPipeCollector,
        *,
        return_code: int | None = None,
        timed_out: bool = False,
    ) -> ProcessCommandResult:
        resolved_code = int(process.returncode if return_code is None else return_code)
        return ProcessCommandResult(
            resolved_code,
            stdout.value,
            stderr.value,
            timed_out=timed_out,
            stdout_bytes=stdout.total_bytes,
            stderr_bytes=stderr.total_bytes,
            stdout_truncated=stdout.truncated,
            stderr_truncated=stderr.truncated,
        )

    async def _execute(
        self,
        context,
        argv: tuple[str, ...],
        timeout_seconds: float | None,
        environment: Mapping[str, str] | None,
        cwd: str | None,
        inherit_stdin: bool,
        inherit_output: bool,
        output_limit_bytes: int,
    ) -> ProcessCommandResult:
        context.checkpoint()
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env=None if environment is None else dict(environment),
                stdin=None if inherit_stdin else asyncio.subprocess.DEVNULL,
                stdout=None if inherit_output else asyncio.subprocess.PIPE,
                stderr=None if inherit_output else asyncio.subprocess.PIPE,
                start_new_session=(os.name == "posix"),
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    if os.name == "nt"
                    else 0
                ),
            )
        except OSError as exc:
            return ProcessCommandResult(
                127,
                b"",
                f"{type(exc).__name__}: {exc}".encode("utf-8", errors="replace"),
                spawn_error=f"{type(exc).__name__}: {exc}",
            )

        stdout = _BoundedPipeCollector(output_limit_bytes)
        stderr = _BoundedPipeCollector(output_limit_bytes)
        try:
            try:
                if timeout_seconds is None:
                    await self._drain_and_wait(process, stdout, stderr)
                else:
                    await asyncio.wait_for(
                        self._drain_and_wait(process, stdout, stderr),
                        timeout=timeout_seconds,
                    )
            except asyncio.TimeoutError:
                await self._terminate_and_drain(process, stdout, stderr)
                return self._result(process, stdout, stderr, return_code=124, timed_out=True)
            context.checkpoint()
            return self._result(process, stdout, stderr)
        except asyncio.CancelledError:
            # A structured cancellation must still physically reap the child and
            # drain its pipes.  After catching the cancellation Python permits
            # cleanup awaits; re-raise only after the owned process has converged.
            await self._terminate_and_drain(process, stdout, stderr)
            raise

    def execute(
        self,
        argv: tuple[str, ...],
        *,
        timeout_seconds: float | None,
        environment: dict[str, str] | None = None,
        cwd: str | None = None,
        inherit_stdin: bool = False,
        inherit_output: bool = False,
        output_limit_bytes: int | None = None,
    ):
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("process command timeout must be positive when specified")
        resolved_limit = (
            self._default_output_limit_bytes
            if output_limit_bytes is None
            else int(output_limit_bytes)
        )
        if resolved_limit <= 0:
            raise ValueError("process command output limit must be positive")
        task_id = self._task_id(argv)
        # ``timeout_seconds`` is child-runtime budget, not queue/admission budget.
        # It starts only after the subprocess has been successfully spawned inside
        # ``_execute``.  Structured owner cancellation remains independent.
        return self._task_group.submit(
            ExecutionSpec(
                task_id=task_id,
                lane_kind=ExecutionLaneKind.ASYNC_IO,
                failure_scope=TaskFailureScope.CALLER,
            ),
            self._execute,
            tuple(str(item) for item in argv),
            None if timeout_seconds is None else float(timeout_seconds),
            environment,
            cwd,
            bool(inherit_stdin),
            bool(inherit_output),
            resolved_limit,
        )


__all__ = ["AsyncProcessCommandRunner"]
