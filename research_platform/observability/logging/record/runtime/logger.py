from __future__ import annotations

import hashlib
import time
from dataclasses import replace
from typing import Mapping

from research_platform.platform.kernel.errors import describe_exception
from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.record.api import LogLevel, LogRecord
from research_platform.observability.logging.sink.api import LogSinkPort


class StructuredLogger:
    """Record-node adapter that emits structured facts to an injected sink."""

    def __init__(self, sink: LogSinkPort, *, logger: str, address: DiagnosticAddress) -> None:
        if not logger.strip():
            raise ValueError("logger must be non-empty")
        self._sink = sink
        self._logger = logger
        self._address = address

    @property
    def address(self) -> DiagnosticAddress:
        return self._address

    def child(
        self,
        *,
        address: DiagnosticAddress | None = None,
        component_id: str | None = None,
    ) -> "StructuredLogger":
        target = address or self._address
        if component_id is not None:
            target = replace(target, component_id=component_id)
        return StructuredLogger(self._sink, logger=self._logger, address=target)

    def log(
        self,
        level: LogLevel,
        *,
        event: str,
        message: str,
        attributes: Mapping[str, object] | None = None,
        correlation_refs: tuple[str, ...] = (),
        artifact_refs: tuple[str, ...] = (),
    ) -> str:
        log_id = self._make_id(level, event, message)
        normalized = tuple(sorted((str(k), self._safe_value(v)) for k, v in (attributes or {}).items()))
        self._sink.append(
            LogRecord(
                log_id=log_id,
                created_at=time.time(),
                level=level,
                logger=self._logger,
                event=event,
                message=message,
                address=self._address,
                attributes=normalized,
                correlation_refs=tuple(dict.fromkeys(correlation_refs)),
                artifact_refs=tuple(dict.fromkeys(artifact_refs)),
            )
        )
        return log_id

    def exception(
        self,
        *,
        event: str,
        message: str,
        exc: BaseException,
        level: LogLevel = LogLevel.ERROR,
        attributes: Mapping[str, object] | None = None,
        correlation_refs: tuple[str, ...] = (),
    ) -> str:
        log_id = self._make_id(level, event, message)
        normalized = tuple(sorted((str(k), self._safe_value(v)) for k, v in (attributes or {}).items()))
        self._sink.append(
            LogRecord(
                log_id=log_id,
                created_at=time.time(),
                level=level,
                logger=self._logger,
                event=event,
                message=message,
                address=self._address,
                attributes=normalized,
                exception=describe_exception(exc),
                correlation_refs=tuple(dict.fromkeys(correlation_refs)),
            )
        )
        return log_id

    @staticmethod
    def _safe_value(value: object) -> str:
        return str(value).replace("\n", "\\n")[:2048]

    def _make_id(self, level: LogLevel, event: str, message: str) -> str:
        raw = "|".join(
            (
                self._logger,
                level.value,
                event,
                message,
                self._address.scope.key,
                self._address.component_id or "",
            )
        )
        digest = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:24]
        return f"log_{digest}"


__all__ = ["StructuredLogger"]
