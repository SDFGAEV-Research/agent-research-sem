from __future__ import annotations

import subprocess


class LinuxChildRegistry:
    """Owns only local ``Popen`` handles for children created by this platform process."""

    def __init__(self) -> None:
        self._children: dict[int, subprocess.Popen[bytes]] = {}

    def remember(self, child: subprocess.Popen[bytes]) -> None:
        self._children[child.pid] = child

    def poll(self, pid: int) -> int | None:
        child = self._children.get(pid)
        return child.poll() if child is not None else None

    def reap(self, pid: int, *, timeout_s: float = 5.0) -> None:
        child = self._children.pop(pid, None)
        if child is None:
            return
        try:
            child.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            pass


__all__ = ["LinuxChildRegistry"]
