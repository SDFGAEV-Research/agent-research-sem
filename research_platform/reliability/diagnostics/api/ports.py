from __future__ import annotations

from typing import ContextManager, Protocol


class DiagnosticIndexSessionPort(Protocol):
    """Consistent read snapshot for compound diagnostic joins."""

    def locate(self, object_id: str) -> dict[str, object] | None: ...
    def last_writer(self, run_id: str, state_name: str) -> dict[str, object] | None: ...
    def around(
        self,
        *,
        run_id: str,
        timestamp: float,
        seconds: float = 30.0,
    ) -> tuple[dict[str, object], ...]: ...
    def recent_state_writers(
        self,
        *,
        run_id: str,
        before: float,
        limit: int = 12,
    ) -> tuple[dict[str, object], ...]: ...
    def related_to(self, object_id: str, *, limit: int = 100) -> tuple[dict[str, object], ...]: ...
    def operation_invocation(self, invocation_id: str) -> dict[str, object] | None: ...
    def unclosed_operations(
        self,
        *,
        run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[dict[str, object], ...]: ...
    def operations_open_at(
        self,
        *,
        run_id: str,
        timestamp: float,
        limit: int = 100,
    ) -> tuple[dict[str, object], ...]: ...


class DiagnosticEvidencePort(Protocol):
    """Read-only diagnostic evidence surface independent of ledger/index backend."""

    @property
    def source_ref(self) -> str: ...

    def verify_authoritative(self) -> dict[str, tuple[int, str]]: ...
    def projection_freshness(
        self,
    ) -> tuple[bool, dict[str, tuple[int, str]], dict[str, tuple[int, str]]]: ...
    def read_session(self) -> ContextManager[DiagnosticIndexSessionPort]: ...
    def locate(self, object_id: str) -> dict[str, object] | None: ...
    def last_writer(self, run_id: str, state_name: str) -> dict[str, object] | None: ...
    def around(
        self,
        *,
        run_id: str,
        timestamp: float,
        seconds: float = 30.0,
    ) -> tuple[dict[str, object], ...]: ...
    def recent_state_writers(
        self,
        *,
        run_id: str,
        before: float,
        limit: int = 12,
    ) -> tuple[dict[str, object], ...]: ...
    def related_to(self, object_id: str, *, limit: int = 100) -> tuple[dict[str, object], ...]: ...
    def unclosed_operations(
        self,
        *,
        run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[dict[str, object], ...]: ...


class MetricQueryPort(Protocol):
    def query(
        self,
        *,
        run_id: str,
        metric: str | None = None,
        decision_cycle_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[dict[str, object], ...]: ...


__all__ = ["DiagnosticEvidencePort", "DiagnosticIndexSessionPort", "MetricQueryPort"]
