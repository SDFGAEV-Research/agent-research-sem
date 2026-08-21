from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Mapping, Sequence

from research_platform.platform.kernel.errors import SafeExceptionDescriptor
from research_platform.observability.logging.context.api import DiagnosticAddress


class LogLevel(StrEnum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class LogRecord:
    """Storage-neutral structured log fact owned by the record node."""

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
    failure_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.log_id.strip():
            raise ValueError("log_id must be non-empty")
        if not self.logger.strip() or not self.event.strip():
            raise ValueError("logger and event must be non-empty")
        if any(not key.strip() for key, _ in self.attributes):
            raise ValueError("log attribute names must be non-empty")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LogBatch:
    records: tuple[LogRecord, ...] = ()

    @classmethod
    def from_sequence(cls, records: Sequence[LogRecord]) -> "LogBatch":
        return cls(tuple(records))


__all__ = ["LogBatch", "LogLevel", "LogRecord"]
