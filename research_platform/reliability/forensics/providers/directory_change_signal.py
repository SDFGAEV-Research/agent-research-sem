from __future__ import annotations

import ctypes
import errno
import os
import struct
import sys
from pathlib import Path

from research_platform.reliability.forensics.providers.hashchain_core import stat_signature


# Linux inotify constants.  They are kept local so the provider has no third-party
# dependency and can use the same state model on the server and on developer hosts.
_IN_CREATE = 0x00000100
_IN_DELETE = 0x00000200
_IN_MOVED_FROM = 0x00000040
_IN_MOVED_TO = 0x00000080
_IN_DELETE_SELF = 0x00000400
_IN_MOVE_SELF = 0x00000800
_IN_UNMOUNT = 0x00002000
_IN_Q_OVERFLOW = 0x00004000
_IN_IGNORED = 0x00008000
_INOTIFY_EVENT = struct.Struct("<iIII")
_DIRECTORY_WATCH_MASK = (
    _IN_CREATE
    | _IN_DELETE
    | _IN_MOVED_FROM
    | _IN_MOVED_TO
    | _IN_DELETE_SELF
    | _IN_MOVE_SELF
)
_DIRECTORY_MUTATION_MASK = (
    _DIRECTORY_WATCH_MASK
    | _IN_UNMOUNT
    | _IN_Q_OVERFLOW
    | _IN_IGNORED
)


def _open_linux_directory_watch(root: Path) -> int | None:
    """Open a non-blocking inotify watch, or return None when unavailable."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        init = getattr(libc, "inotify_init1")
        add_watch = getattr(libc, "inotify_add_watch")
        init.argtypes = [ctypes.c_int]
        init.restype = ctypes.c_int
        add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        add_watch.restype = ctypes.c_int
        flags = os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
        fd = int(init(flags))
        if fd < 0:
            return None
        watch = int(add_watch(fd, os.fsencode(root), _DIRECTORY_WATCH_MASK))
        if watch < 0:
            os.close(fd)
            return None
        return fd
    except (AttributeError, OSError, TypeError):
        return None


class DirectoryChangeSignal:
    """Detect directory-entry mutations without enumerating the directory.

    Linux production uses the kernel event queue.  Filesystems/platforms without
    inotify use the directory stat as a portable fallback.  The caller owns the
    authoritative expected signature; this object only owns the event cursor and
    a fail-closed pending bit.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._fd = _open_linux_directory_watch(root)
        self._pending = False

    @property
    def mode(self) -> str:
        return "inotify" if self._fd is not None else "stat"

    def _drain_events(self) -> bool:
        if self._fd is None:
            return False
        changed = False
        while True:
            try:
                data = os.read(self._fd, 64 * 1024)
            except BlockingIOError:
                return changed
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                self._pending = True
                return True
            if not data:
                return changed
            offset = 0
            while offset < len(data):
                if len(data) - offset < _INOTIFY_EVENT.size:
                    self._pending = True
                    return True
                _watch_descriptor, mask, _cookie, name_length = _INOTIFY_EVENT.unpack_from(
                    data, offset
                )
                record_length = _INOTIFY_EVENT.size + name_length
                if record_length > len(data) - offset:
                    self._pending = True
                    return True
                if mask & _DIRECTORY_MUTATION_MASK:
                    changed = True
                offset += record_length

    def changed_since(
        self,
        expected_signature: tuple[int, int, int, int] | None,
    ) -> bool:
        """Return whether an unacknowledged external mutation is observable."""
        if self._pending:
            return True
        if self._drain_events():
            self._pending = True
            return True
        if self._fd is None and stat_signature(self.root) != expected_signature:
            self._pending = True
            return True
        return False

    def acknowledge(self) -> None:
        """Consume mutations caused by the owning writer and clear the latch."""
        self._drain_events()
        self._pending = False

    def close(self) -> None:
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


__all__ = ["DirectoryChangeSignal"]
