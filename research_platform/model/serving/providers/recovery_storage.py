from __future__ import annotations

import json
from pathlib import Path

from research_platform.platform.kernel import canonical_bytes

from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes
from research_platform.platform.kernel.durability.file_lock import InterprocessFileLock

from ..api.recovery_state import DurableRecoveryAttempt, DurableRecoveryPhase


class FileDurableRecoveryStore:
    """Single-record filesystem backend for one recovery attempt."""

    def __init__(self, path: Path, *, guard_path: Path) -> None:
        self._path = path
        self._guard_path = guard_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._guard_path.parent.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return self._path.exists()

    @staticmethod
    def _encode(attempt: DurableRecoveryAttempt) -> bytes:
        return canonical_bytes(attempt, indent=2)

    def create(self, attempt: DurableRecoveryAttempt) -> None:
        with InterprocessFileLock(self._guard_path):
            if self._path.exists():
                raise RuntimeError("recovery attempt already exists; reconcile it instead of overwriting")
            atomic_replace_bytes(self._path, self._encode(attempt))

    def write(self, attempt: DurableRecoveryAttempt) -> None:
        with InterprocessFileLock(self._guard_path):
            if not self._path.exists():
                raise RuntimeError("recovery attempt does not exist")
            atomic_replace_bytes(self._path, self._encode(attempt))

    def load(self) -> DurableRecoveryAttempt:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        data["phase"] = DurableRecoveryPhase(data["phase"])
        data["completed_steps"] = tuple(data["completed_steps"])
        data["evidence_refs"] = tuple(data["evidence_refs"])
        return DurableRecoveryAttempt(**data)


__all__ = ["FileDurableRecoveryStore"]
