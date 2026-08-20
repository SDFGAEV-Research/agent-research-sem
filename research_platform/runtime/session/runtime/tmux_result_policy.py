from __future__ import annotations

import hashlib

from research_platform.platform.kernel.errors import redact_text

from .tmux_contracts import TmuxCommandResult


class TmuxCommandFailed(RuntimeError):
    """Safe transport failure. Raw stderr is never stored on the exception."""

    def __init__(self, operation: str, result: TmuxCommandResult) -> None:
        safe = redact_text(result.stderr.strip() or result.stdout.strip() or "tmux command failed")
        digest = hashlib.sha256(safe.encode("utf-8", "replace")).hexdigest()
        self.operation = operation
        self.returncode = int(result.returncode)
        self.stderr_digest = digest
        super().__init__(
            f"tmux {operation} failed rc={self.returncode}: {safe}; stderr_digest={digest}"
        )


_MISSING_MARKERS = (
    "can't find session",
    "no server running on",
    "no sessions",
)


def session_is_absent(result: TmuxCommandResult) -> bool:
    if result.returncode == 0:
        return False
    text = f"{result.stderr}\n{result.stdout}".strip().lower()
    # Literal "missing" is accepted for deterministic fake transports used by
    # tests and adapters, while partial matches are intentionally rejected.
    if text == "missing":
        return True
    return any(marker in text for marker in _MISSING_MARKERS)


def require_success(operation: str, result: TmuxCommandResult) -> None:
    if result.returncode != 0:
        raise TmuxCommandFailed(operation, result)


__all__ = ["TmuxCommandFailed", "require_success", "session_is_absent"]
