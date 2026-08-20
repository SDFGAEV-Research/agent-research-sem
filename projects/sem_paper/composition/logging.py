from __future__ import annotations

from research_platform.observability.logging.api import LogSinkPort

from projects.sem_paper.policies.logging import SemPaperLogSink


def bind_project_logging(downstream: LogSinkPort) -> LogSinkPort:
    """Apply Paper-1 logging policy to an injected Logging System sink."""

    return SemPaperLogSink(downstream)


__all__ = ["bind_project_logging"]
