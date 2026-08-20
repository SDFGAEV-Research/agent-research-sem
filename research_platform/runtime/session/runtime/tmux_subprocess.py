from __future__ import annotations

import subprocess
from typing import Mapping

from .tmux_contracts import TmuxCommandResult, TmuxCommandTimeout


class SubprocessTmuxCommandRunner:
    """Sole real tmux subprocess execution authority."""

    def __init__(self, timeout_s: float = 5.0) -> None:
        if timeout_s <= 0:
            raise ValueError("tmux command timeout must be positive")
        self.timeout_s = float(timeout_s)

    def run(self, argv: tuple[str, ...], *, environment: Mapping[str, str]) -> TmuxCommandResult:
        try:
            completed = subprocess.run(
                argv,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                shell=False,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise TmuxCommandTimeout(
                f"tmux command exceeded {self.timeout_s:.3f}s timeout"
            ) from exc
        return TmuxCommandResult(completed.returncode, completed.stdout, completed.stderr)


__all__ = ["SubprocessTmuxCommandRunner"]
