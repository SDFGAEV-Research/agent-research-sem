from __future__ import annotations

from pathlib import Path
import os
import subprocess
from typing import Mapping

from .api import (
    LocalCommandResult,
    LocalCommandStartError,
    LocalCommandRunnerPort,
    LocalCommandTimeoutError,
)


class SubprocessLocalCommandRunner(LocalCommandRunnerPort):
    """The sole local subprocess authority used by platform providers."""

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> LocalCommandResult:
        if not argv:
            raise ValueError("local command argv must be non-empty")
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("local command timeout must be positive")
        process_environment = None
        if environment is not None:
            process_environment = os.environ.copy()
            process_environment.update({str(key): str(value) for key, value in environment.items()})
        try:
            completed = subprocess.run(
                argv,
                cwd=str(cwd) if cwd is not None else None,
                env=process_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise LocalCommandTimeoutError(
                "local-command",
                f"execution exceeded {timeout_seconds:g}s",
            ) from exc
        except OSError as exc:
            raise LocalCommandStartError(
                "local-command",
                f"could not start ({type(exc).__name__})",
            ) from exc
        return LocalCommandResult(
            argv=argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


__all__ = ["SubprocessLocalCommandRunner"]
