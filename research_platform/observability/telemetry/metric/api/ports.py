from __future__ import annotations

from typing import Protocol

from research_platform.platform.kernel import ExecutionContext

from .rows import PendingMetric


StorageMetricRow = tuple[object, ...]


class PendingMetricWriteSessionPort(Protocol):
    def insert_many(self, rows: tuple[PendingMetric, ...]) -> tuple[int, ...]: ...
    def close(self) -> None: ...


class TelemetryBatchStorePort(Protocol):
    def prepare(self, context: ExecutionContext, name: str, value: float, **dimensions: str) -> PendingMetric: ...
    def writer_session(self) -> PendingMetricWriteSessionPort: ...


class TelemetryPersistenceWriteSessionPort(Protocol):
    def insert_many(self, values: tuple[StorageMetricRow, ...]) -> tuple[int, ...]: ...
    def close(self) -> None: ...


class TelemetryPersistencePort(Protocol):
    def insert_many(self, values: tuple[StorageMetricRow, ...]) -> tuple[int, ...]: ...
    def writer_session(self) -> TelemetryPersistenceWriteSessionPort: ...
    def query(
        self,
        *,
        run_id: str,
        metric: str | None,
        decision_cycle_id: str | None,
        limit: int,
    ) -> tuple[StorageMetricRow, ...]: ...
    def count(self) -> int: ...


__all__ = [
    "PendingMetricWriteSessionPort",
    "StorageMetricRow",
    "TelemetryBatchStorePort",
    "TelemetryPersistencePort",
    "TelemetryPersistenceWriteSessionPort",
]
