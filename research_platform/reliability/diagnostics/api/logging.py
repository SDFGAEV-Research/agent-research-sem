from __future__ import annotations

from typing import Protocol

from research_platform.observability.logging.api import LogLevel, LogRecord
from research_platform.scope.api import ScopeIdentity
from research_platform.governance.system_registry.api import SystemIdentity


class DiagnosticLogQueryPort(Protocol):
    """Read-only diagnostic projection over structured log records."""

    def query_logs(
        self,
        *,
        scope: ScopeIdentity | None = None,
        system: SystemIdentity | None = None,
        component_id: str | None = None,
        trace_id: str | None = None,
        level_at_least: LogLevel | None = None,
        event: str | None = None,
        limit: int = 1000,
    ) -> tuple[LogRecord, ...]: ...


__all__ = ["DiagnosticLogQueryPort"]
