from __future__ import annotations

import asyncio
from concurrent.futures import Future
import inspect
from threading import Condition, Event, Lock, Thread
import time
from typing import Any, Callable, Generic, TypeVar

from research_platform.platform.concurrency.api import CancellationTokenPort, Deadline, TaskCancelled

T = TypeVar("T")


class _AsyncFutureHandle(Generic[T]):
    def __init__(self, future: Future[T]) -> None:
        self._future = future
        self._completion_lock = Lock()
        self._completed_monotonic: float | None = None
        future.add_done_callback(self._capture_completion)

    def _capture_completion(self, _future: Future[T]) -> None:
        with self._completion_lock:
            if self._completed_monotonic is None:
                self._completed_monotonic = time.monotonic()

    def done(self) -> bool: return self._future.done()
    def running(self) -> bool: return self._future.running()
    def cancel(self) -> bool: return self._future.cancel()
    def cancelled(self) -> bool: return self._future.cancelled()
    def result(self, timeout: float | None = None) -> T: return self._future.result(timeout=timeout)
    def add_done_callback(self, callback: Callable[["_AsyncFutureHandle[T]"], None]) -> None:
        self._future.add_done_callback(lambda _future: callback(self))

    @property
    def completed_monotonic(self) -> float | None:
        with self._completion_lock:
            return self._completed_monotonic


class AsyncIoExecutor:
    """One event-loop thread with bounded coroutine submission capacity.

    The loop is provider-owned and business systems cannot create tasks directly.
    Every coroutine enters through TaskGroup ownership, so cancellation/deadline
    state remains visible in the same topology as thread/process/serial work.
    """

    _ADMISSION_POLL_SECONDS = 0.05

    def __init__(self, *, max_in_flight: int, thread_name: str = "platform-async-io", shutdown_timeout_seconds: float = 30.0) -> None:
        if max_in_flight <= 0:
            raise ValueError("async I/O max_in_flight must be positive")
        if shutdown_timeout_seconds <= 0:
            raise ValueError("async I/O shutdown timeout must be positive")
        self._max_in_flight = int(max_in_flight)
        self._available = int(max_in_flight)
        self._shutdown_timeout_seconds = float(shutdown_timeout_seconds)
        self._condition = Condition()
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._ready = Event()
        self._thread = Thread(target=self._run, name=thread_name, daemon=False)
        self._futures: set[Future[Any]] = set()
        self._thread.start()
        if not self._ready.wait(self._shutdown_timeout_seconds):
            raise RuntimeError("async I/O event loop failed to start")

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    @staticmethod
    def _cancelled(cancellation: CancellationTokenPort | None) -> bool:
        return cancellation is not None and cancellation.cancelled

    def _acquire(self, *, deadline: Deadline | None, cancellation: CancellationTokenPort | None) -> None:
        with self._condition:
            while self._available <= 0:
                if self._closed:
                    raise RuntimeError("async I/O executor is closed")
                if self._cancelled(cancellation):
                    raise TaskCancelled(cancellation.reason or "async I/O capacity wait cancelled")
                remaining = None if deadline is None else deadline.remaining_seconds
                if remaining is not None and remaining <= 0:
                    raise TimeoutError("async I/O capacity wait deadline expired")
                wait_for = self._ADMISSION_POLL_SECONDS if remaining is None else min(self._ADMISSION_POLL_SECONDS, remaining)
                self._condition.wait(wait_for)
            if self._closed:
                raise RuntimeError("async I/O executor is closed")
            if self._cancelled(cancellation):
                raise TaskCancelled(cancellation.reason or "async I/O capacity wait cancelled")
            if deadline is not None and deadline.expired:
                raise TimeoutError("async I/O capacity wait deadline expired")
            self._available -= 1

    def _release(self, future: Future[Any]) -> None:
        with self._condition:
            self._futures.discard(future)
            self._available += 1
            if self._available > self._max_in_flight:
                raise RuntimeError("async I/O capacity accounting overflow")
            self._condition.notify_all()

    def submit(
        self,
        fn: Callable[..., T],
        /,
        *args: Any,
        deadline: Deadline | None = None,
        cancellation: CancellationTokenPort | None = None,
        **kwargs: Any,
    ) -> _AsyncFutureHandle[T]:
        self._acquire(deadline=deadline, cancellation=cancellation)

        async def invoke() -> T:
            value = fn(*args, **kwargs)
            if not inspect.isawaitable(value):
                raise TypeError("ASYNC_IO execution callable must return an awaitable")
            return await value

        try:
            future = asyncio.run_coroutine_threadsafe(invoke(), self._loop)
        except BaseException:
            with self._condition:
                self._available += 1
                self._condition.notify_all()
            raise
        # Register ownership before attaching the completion callback.
        # ``Future.add_done_callback`` executes immediately for an already-complete
        # future; doing this in the opposite order can release the capacity slot
        # and then re-add a dead future to ``_futures``, leaking shutdown state.
        with self._condition:
            self._futures.add(future)
            if self._closed:
                future.cancel()
        future.add_done_callback(self._release)
        return _AsyncFutureHandle(future)

    async def _cancel_all_tasks(self) -> None:
        current = asyncio.current_task()
        tasks = [task for task in asyncio.all_tasks() if task is not current and not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def close(self, *, wait: bool = True, cancel_pending: bool = False) -> None:
        with self._condition:
            already_closed = self._closed
            self._closed = True
            futures = tuple(self._futures)
            self._condition.notify_all()
        if cancel_pending:
            for future in futures:
                future.cancel()
        if self._thread.is_alive() and not already_closed:
            shutdown = asyncio.run_coroutine_threadsafe(self._cancel_all_tasks(), self._loop)
            if wait:
                try:
                    shutdown.result(timeout=self._shutdown_timeout_seconds)
                finally:
                    self._loop.call_soon_threadsafe(self._loop.stop)
            else:
                shutdown.add_done_callback(lambda _future: self._loop.call_soon_threadsafe(self._loop.stop))
        elif self._thread.is_alive() and wait:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if wait:
            self._thread.join(timeout=self._shutdown_timeout_seconds)
            if self._thread.is_alive():
                raise TimeoutError("async I/O executor did not terminate")


__all__ = ["AsyncIoExecutor"]
