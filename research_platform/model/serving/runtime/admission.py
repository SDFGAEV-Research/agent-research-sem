from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Condition, Lock
import time

from research_platform.platform.concurrency.api import CancellationTokenPort, TaskCancelled


class ModelAdmissionTimeout(TimeoutError):
    pass


class ModelAdmissionClosed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdmissionSnapshot:
    capacity: int
    active: int
    waiting: int


class AdmissionLease:
    def __init__(self, controller: "ModelAdmissionController") -> None:
        self._controller = controller
        self._released = False
        self._release_lock = Lock()

    def release(self) -> None:
        with self._release_lock:
            if self._released:
                return
            self._released = True
        self._controller._release()

    def __enter__(self) -> "AdmissionLease":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class ModelAdmissionController:
    """FIFO backpressure with cancellation and shutdown awareness."""

    _ADMISSION_POLL_SECONDS = 0.05

    def __init__(self, qualified_capacity: int) -> None:
        if qualified_capacity <= 0:
            raise ValueError("qualified capacity must be positive")
        self.capacity = qualified_capacity
        self._active = 0
        self._waiters: deque[object] = deque()
        self._cv = Condition()
        self._closed = False

    @staticmethod
    def _cancelled(cancellation: CancellationTokenPort | None) -> bool:
        return cancellation is not None and cancellation.cancelled

    @staticmethod
    def _cancel_reason(cancellation: CancellationTokenPort | None) -> str:
        return (
            cancellation.reason
            if cancellation is not None and cancellation.reason
            else "model admission cancelled"
        )

    def acquire(
        self,
        timeout_seconds: float | None = None,
        *,
        cancellation: CancellationTokenPort | None = None,
    ) -> AdmissionLease:
        if timeout_seconds is not None and timeout_seconds < 0:
            raise ValueError("model admission timeout cannot be negative")
        deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        ticket = object()
        admitted = False
        with self._cv:
            if self._closed:
                raise ModelAdmissionClosed("model admission controller is closed")
            self._waiters.append(ticket)
            try:
                while True:
                    if self._closed:
                        raise ModelAdmissionClosed("model admission controller is closed")
                    if self._cancelled(cancellation):
                        raise TaskCancelled(self._cancel_reason(cancellation))
                    is_head = bool(self._waiters) and self._waiters[0] is ticket
                    if is_head and self._active < self.capacity:
                        self._waiters.popleft()
                        self._active += 1
                        admitted = True
                        self._cv.notify_all()
                        return AdmissionLease(self)
                    remaining = None if deadline is None else deadline - time.monotonic()
                    if remaining is not None and remaining <= 0:
                        raise ModelAdmissionTimeout(
                            "model admission timed out; no quality fallback was attempted"
                        )
                    wait_for = self._ADMISSION_POLL_SECONDS
                    if remaining is not None:
                        wait_for = min(wait_for, remaining)
                    self._cv.wait(wait_for)
            finally:
                if not admitted:
                    try:
                        self._waiters.remove(ticket)
                    except ValueError:
                        pass
                    self._cv.notify_all()

    def _release(self) -> None:
        with self._cv:
            if self._active <= 0:
                raise RuntimeError("admission lease underflow")
            self._active -= 1
            self._cv.notify_all()

    def close(self) -> None:
        """Reject new admission and wake all blocked waiters."""
        with self._cv:
            if self._closed:
                return
            self._closed = True
            self._cv.notify_all()

    @property
    def closed(self) -> bool:
        with self._cv:
            return self._closed

    def snapshot(self) -> AdmissionSnapshot:
        with self._cv:
            return AdmissionSnapshot(self.capacity, self._active, len(self._waiters))


__all__ = [
    "AdmissionLease",
    "AdmissionSnapshot",
    "ModelAdmissionClosed",
    "ModelAdmissionController",
    "ModelAdmissionTimeout",
]
