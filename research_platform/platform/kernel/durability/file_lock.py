from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType

try:
    import fcntl
except ImportError:  # pragma: no cover - production server target is POSIX/Linux.
    fcntl = None  # type: ignore[assignment]


class InterprocessLockUnavailable(RuntimeError):
    pass


class InterprocessLockBusy(RuntimeError):
    pass


class InterprocessFileLock:
    """Small POSIX advisory lock for cross-process read/modify/write guards.

    The lock file is intentionally persistent.  Unlinking a lock file while
    another process holds the inode can create two independent lock domains.
    Process exit releases the kernel lock automatically.
    """

    def __init__(self, path: Path, *, blocking: bool = True) -> None:
        self.path = path
        self.blocking = blocking
        self._fd: int | None = None

    def __enter__(self) -> "InterprocessFileLock":
        if fcntl is None:
            raise InterprocessLockUnavailable("cross-process file locking requires POSIX fcntl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            flags = fcntl.LOCK_EX if self.blocking else (fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, flags)
        except BlockingIOError as exc:
            os.close(fd)
            raise InterprocessLockBusy(f"interprocess lock busy: {self.path}") from exc
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
        fd = self._fd
        self._fd = None
        if fd is None:
            return
        assert fcntl is not None
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


__all__ = ["InterprocessFileLock", "InterprocessLockBusy", "InterprocessLockUnavailable"]
