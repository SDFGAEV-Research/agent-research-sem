from __future__ import annotations

from research_platform.observability.logging.query.api import LogQueryPort
from research_platform.observability.logging.record.api import ExceptionDescriptorPort, LoggingSystemPort
from research_platform.observability.logging.record.providers.exception_descriptor import KernelExceptionDescriptor
from research_platform.observability.logging.record.runtime import StructuredLoggingSystem
from research_platform.observability.logging.sink.api import LogSinkPort


def build_logging_system(
    sink: LogSinkPort,
    query: LogQueryPort,
    *,
    exception_descriptor: ExceptionDescriptorPort | None = None,
) -> LoggingSystemPort:
    return StructuredLoggingSystem(
        sink,
        query,
        exception_descriptor=exception_descriptor or KernelExceptionDescriptor(),
    )


__all__ = ["build_logging_system"]
