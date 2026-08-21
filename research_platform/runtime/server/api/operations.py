from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ServerOperationKind(StrEnum):
    COMMAND = "command"
    FILE_UPLOAD = "file_upload"
    INTERACTIVE_ATTACH = "interactive_attach"


class ServerOperationState(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class ServerOperationStarted:
    operation_id: str
    server_id: str
    kind: ServerOperationKind
    request_digest: str
    started_at: float
    interactive: bool
    profile_digest: str = ""


@dataclass(frozen=True, slots=True)
class ServerOperationFinished:
    operation_id: str
    server_id: str
    kind: ServerOperationKind
    request_digest: str
    state: ServerOperationState
    finished_at: float
    duration_seconds: float
    return_code: int | None
    failure_kind: str
    stdout_bytes: int
    stderr_bytes: int
    error_type: str | None = None
    error_digest: str | None = None
    profile_digest: str = ""
    stdout_digest: str = ""
    stderr_digest: str = ""


class ServerOperationJournalPort(Protocol):
    """Durable observation boundary for every managed server side effect."""

    def record_started(self, event: ServerOperationStarted) -> None: ...

    def record_finished(self, event: ServerOperationFinished) -> None: ...


__all__ = [
    "ServerOperationFinished",
    "ServerOperationJournalPort",
    "ServerOperationKind",
    "ServerOperationStarted",
    "ServerOperationState",
]
