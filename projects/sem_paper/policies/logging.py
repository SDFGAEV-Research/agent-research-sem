from __future__ import annotations

from dataclasses import replace

from research_platform.observability.logging.record.api import LogRecord
from research_platform.observability.logging.sink.api import LogSinkPort


class SemPaperLogSink:
    """Paper-1 log policy expressed purely through the Logging System API.

    The project enriches every record with stable project/paper context but does not
    know where records are stored or which logging runtime produced them.
    """

    def __init__(self, downstream: LogSinkPort) -> None:
        self._downstream = downstream

    def append(self, record: LogRecord) -> None:
        attributes = dict(record.attributes)
        attributes.setdefault("project_id", "sem-paper-1")
        attributes.setdefault("paper_method", "self_evolving_memory")
        self._downstream.append(replace(record, attributes=tuple(sorted(attributes.items()))))


__all__ = ["SemPaperLogSink"]
