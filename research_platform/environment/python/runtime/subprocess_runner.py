from __future__ import annotations

from pathlib import Path
import os
import subprocess
from typing import Mapping

from research_platform.environment.python.api import EnvironmentCommandResult


class SubprocessEnvironmentCommandRunner:
    """Single local command authority for environment-management backends."""

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> EnvironmentCommandResult:
        process_environment = None
        if environment is not None:
            process_environment = os.environ.copy()
            process_environment.update({str(key): str(value) for key, value in environment.items()})
        completed = subprocess.run(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            env=process_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return EnvironmentCommandResult(
            argv=argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


__all__ = ["SubprocessEnvironmentCommandRunner"]
