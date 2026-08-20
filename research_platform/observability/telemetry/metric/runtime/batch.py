from __future__ import annotations

from threading import RLock

from research_platform.platform.kernel import ExecutionContext

from ..api.rows import PendingMetric
from ..api.ports import PendingMetricWriteSessionPort, TelemetryBatchStorePort


class TelemetryBatchRecorder:
    """Hot-path recorder with one reusable writer session per recorder lifecycle."""

    def __init__(self, store: TelemetryBatchStorePort, batch_size: int = 128) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.store = store
        self.batch_size = batch_size
        self._pending: list[PendingMetric] = []
        self._lock = RLock()
        self._closed = False
        self._session: PendingMetricWriteSessionPort = store.writer_session()

    def observe(self, context: ExecutionContext, name: str, value: float, **dimensions: str) -> None:
        row = self.store.prepare(context, name, value, **dimensions)
        with self._lock:
            if self._closed:
                raise RuntimeError("telemetry recorder is closed")
            self._pending.append(row)
            if len(self._pending) >= self.batch_size:
                self._flush_locked()

    def _flush_locked(self) -> tuple[int, ...]:
        batch = tuple(self._pending)
        if not batch:
            return ()
        ids = self._session.insert_many(batch)
        del self._pending[:len(batch)]
        return ids

    def flush(self) -> tuple[int, ...]:
        with self._lock:
            if self._closed:
                return ()
            return self._flush_locked()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                try:
                    self._flush_locked()
                finally:
                    self._session.close()
                    self._closed = True

    @property
    def buffered(self) -> int:
        with self._lock:
            return len(self._pending)

    def __enter__(self) -> "TelemetryBatchRecorder":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = ["TelemetryBatchRecorder"]
