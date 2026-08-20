from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Protocol, Sequence

from research_platform.platform.kernel.errors import SafeExceptionDescriptor
from research_platform.scope.api import ScopeIdentity
from research_platform.governance.system_registry.api import SystemIdentity


class LogLevel(StrEnum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class DiagnosticAddress:
    """Stable location of a diagnostic fact inside the platform hierarchy."""

    scope_path: tuple[ScopeIdentity, ...]
    system_path: tuple[SystemIdentity, ...] = ()
    component_id: str | None = None
    operation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None

    def __post_init__(self) -> None:
        if not self.scope_path:
            raise ValueError("diagnostic address requires at least one scope")
        if any(not scope.scope_id.strip() for scope in self.scope_path):
            raise ValueError("diagnostic scope identities must be non-empty")
        if any(not system.key.strip() for system in self.system_path):
            raise ValueError("diagnostic system identities must be non-empty")
        if self.component_id is not None and not self.component_id.strip():
            raise ValueError("component_id must be non-empty when supplied")

    @property
    def scope(self) -> ScopeIdentity:
        return self.scope_path[-1]

    @property
    def system(self) -> SystemIdentity | None:
        return self.system_path[-1] if self.system_path else None


@dataclass(frozen=True, slots=True)
class LogRecord:
    """Storage-neutral structured log fact. It is observational, not authoritative truth."""

    log_id: str
    created_at: float
    level: LogLevel
    logger: str
    event: str
    message: str
    address: DiagnosticAddress
    attributes: tuple[tuple[str, str], ...] = ()
    exception: SafeExceptionDescriptor | None = None
    correlation_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.log_id.strip():
            raise ValueError("log_id must be non-empty")
        if not self.logger.strip() or not self.event.strip():
            raise ValueError("logger and event must be non-empty")
        if any(not key.strip() for key, _ in self.attributes):
            raise ValueError("log attribute names must be non-empty")


class LogSinkPort(Protocol):
    def append(self, record: LogRecord) -> None: ...


class LogQueryPort(Protocol):
    def query(
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


@dataclass(frozen=True, slots=True)
class LogBatch:
    records: tuple[LogRecord, ...] = ()

    @classmethod
    def from_sequence(cls, records: Sequence[LogRecord]) -> "LogBatch":
        return cls(tuple(records))


__all__ = [
    "DiagnosticAddress",
    "LogBatch",
    "LogLevel",
    "LogQueryPort",
    "LogRecord",
    "LogSinkPort",
]
