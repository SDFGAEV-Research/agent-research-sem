from __future__ import annotations

from pathlib import Path
from typing import Mapping

from research_platform.environment.python.api import EnvironmentCommandResult
from research_platform.platform.kernel.process import (
    LocalCommandRunnerPort,
    SubprocessLocalCommandRunner,
)


class SubprocessEnvironmentCommandRunner:
    """Environment adapter over the platform-wide local process authority."""

    def __init__(self, runner: LocalCommandRunnerPort | None = None) -> None:
        self._runner = runner or SubprocessLocalCommandRunner()

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> EnvironmentCommandResult:
        completed = self._runner.run(argv, cwd=cwd, environment=environment)
        return EnvironmentCommandResult(
            argv=completed.argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


__all__ = ["SubprocessEnvironmentCommandRunner"]
