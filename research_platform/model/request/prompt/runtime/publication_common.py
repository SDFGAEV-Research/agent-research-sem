from __future__ import annotations

import hashlib
import os
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - deployment target is POSIX
    fcntl = None


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fsync_dir(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class PromptPublicationError(RuntimeError):
    pass


class PromptPublicationLease:
    """One kernel-backed writer lease shared by staging and promotion transactions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.fh = None

    def __enter__(self):
        if fcntl is None:
            raise RuntimeError("prompt publication lease requires fcntl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = self.path.open("a+b")
        try:
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.fh.close()
            raise PromptPublicationError("another prompt publication is active") from exc
        return self

    def __exit__(self, *exc):
        assert self.fh is not None
        fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        self.fh.close()
