from __future__ import annotations

import hashlib
from pathlib import Path
import time
from uuid import uuid4

from research_platform.runtime.server.api import (
    ServerOperationFinished,
    ServerOperationJournalPort,
    ServerOperationKind,
    ServerOperationStarted,
    ServerOperationState,
)
from research_platform.runtime.server.identity.api import (
    ServerCommandResult,
    ServerConnectionPort,
    ServerFileTransferPort,
    ServerFileTransferResult,
    ServerTransportFailureKind,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _error_fields(exc: BaseException) -> tuple[str, str]:
    return type(exc).__name__, _digest(str(exc))


def _operation_id() -> str:
    return f"srv-op-{uuid4().hex}"


class ObservedServerConnection(ServerConnectionPort):
    """Connection decorator that journals every remote command boundary."""

    def __init__(
        self,
        connection: ServerConnectionPort,
        journal: ServerOperationJournalPort,
        *,
        profile_digest: str = "",
    ) -> None:
        self._connection = connection
        self._journal = journal
        self._profile_digest = profile_digest

    @property
    def profile(self):
        return self._connection.profile

    def execute(self, command: str, *, interactive: bool = False) -> ServerCommandResult:
        operation_id = _operation_id()
        request_digest = _digest(command)
        started_at = time.time()
        started_clock = time.perf_counter()
        self._journal.record_started(
            ServerOperationStarted(
                operation_id,
                self.profile.server_id,
                ServerOperationKind.COMMAND,
                request_digest,
                started_at,
                interactive,
                self._profile_digest,
            )
        )
        try:
            result = self._connection.execute(command, interactive=interactive)
        except BaseException as exc:
            error_type, error_digest = _error_fields(exc)
            self._journal.record_finished(
                ServerOperationFinished(
                    operation_id,
                    self.profile.server_id,
                    ServerOperationKind.COMMAND,
                    request_digest,
                    ServerOperationState.FAILED,
                    time.time(),
                    time.perf_counter() - started_clock,
                    None,
                    type(exc).__name__,
                    0,
                    0,
                    error_type,
                    error_digest,
                    self._profile_digest,
                )
            )
            raise
        state = (
            ServerOperationState.SUCCEEDED
            if result.succeeded
            else ServerOperationState.TIMED_OUT
            if result.failure_kind == ServerTransportFailureKind.TIMEOUT
            else ServerOperationState.FAILED
        )
        self._journal.record_finished(
            ServerOperationFinished(
                operation_id,
                self.profile.server_id,
                ServerOperationKind.COMMAND,
                request_digest,
                state,
                time.time(),
                result.duration_seconds or (time.perf_counter() - started_clock),
                result.return_code,
                result.failure_kind.value,
                result.stdout_bytes or len(result.stdout.encode("utf-8", errors="replace")),
                result.stderr_bytes or len(result.stderr.encode("utf-8", errors="replace")),
                profile_digest=self._profile_digest,
                stdout_digest=_digest(result.stdout),
                stderr_digest=_digest(result.stderr),
            )
        )
        return result

    def interactive_argv(
        self,
        command: str,
        *,
        allocate_tty: bool = False,
    ) -> tuple[str, ...]:
        return self._connection.interactive_argv(command, allocate_tty=allocate_tty)

    def run_interactive(self, argv: tuple[str, ...]) -> int:
        operation_id = _operation_id()
        request_digest = _digest("interactive-attach\0" + "\0".join(argv))
        started_clock = time.perf_counter()
        self._journal.record_started(
            ServerOperationStarted(
                operation_id,
                self.profile.server_id,
                ServerOperationKind.INTERACTIVE_ATTACH,
                request_digest,
                time.time(),
                True,
                self._profile_digest,
            )
        )
        try:
            return_code = self._connection.run_interactive(argv)
        except BaseException as exc:
            error_type, error_digest = _error_fields(exc)
            self._journal.record_finished(
                ServerOperationFinished(
                    operation_id,
                    self.profile.server_id,
                    ServerOperationKind.INTERACTIVE_ATTACH,
                    request_digest,
                    ServerOperationState.FAILED,
                    time.time(),
                    time.perf_counter() - started_clock,
                    None,
                    error_type,
                    0,
                    0,
                    error_type,
                    error_digest,
                    self._profile_digest,
                )
            )
            raise
        self._journal.record_finished(
            ServerOperationFinished(
                operation_id,
                self.profile.server_id,
                ServerOperationKind.INTERACTIVE_ATTACH,
                request_digest,
                ServerOperationState.SUCCEEDED if return_code == 0 else ServerOperationState.FAILED,
                time.time(),
                time.perf_counter() - started_clock,
                return_code,
                "none" if return_code == 0 else "remote_exit",
                0,
                0,
                profile_digest=self._profile_digest,
            )
        )
        return return_code


class ObservedServerFileTransfer(ServerFileTransferPort):
    """File-transfer decorator sharing the same operation ledger."""

    def __init__(
        self,
        transfer: ServerFileTransferPort,
        journal: ServerOperationJournalPort,
        *,
        profile_digest: str = "",
    ) -> None:
        self._transfer = transfer
        self._journal = journal
        self._profile_digest = profile_digest

    @property
    def profile(self):
        return self._transfer.profile

    def upload(
        self,
        local_path: str,
        remote_path: str,
        *,
        interactive: bool = False,
    ) -> ServerFileTransferResult:
        local = Path(local_path).expanduser().resolve()
        try:
            size = local.stat().st_size
        except OSError:
            size = -1
        request_digest = _digest(f"{local}\0{remote_path}\0{size}")
        operation_id = _operation_id()
        started_clock = time.perf_counter()
        self._journal.record_started(
            ServerOperationStarted(
                operation_id,
                self.profile.server_id,
                ServerOperationKind.FILE_UPLOAD,
                request_digest,
                time.time(),
                interactive,
                self._profile_digest,
            )
        )
        try:
            result = self._transfer.upload(
                local_path,
                remote_path,
                interactive=interactive,
            )
        except BaseException as exc:
            error_type, error_digest = _error_fields(exc)
            self._journal.record_finished(
                ServerOperationFinished(
                    operation_id,
                    self.profile.server_id,
                    ServerOperationKind.FILE_UPLOAD,
                    request_digest,
                    ServerOperationState.FAILED,
                    time.time(),
                    time.perf_counter() - started_clock,
                    None,
                    type(exc).__name__,
                    0,
                    0,
                    error_type,
                    error_digest,
                    self._profile_digest,
                )
            )
            raise
        state = (
            ServerOperationState.SUCCEEDED
            if result.succeeded
            else ServerOperationState.TIMED_OUT
            if result.failure_kind == ServerTransportFailureKind.TIMEOUT
            else ServerOperationState.FAILED
        )
        self._journal.record_finished(
            ServerOperationFinished(
                operation_id,
                self.profile.server_id,
                ServerOperationKind.FILE_UPLOAD,
                request_digest,
                state,
                time.time(),
                result.duration_seconds or (time.perf_counter() - started_clock),
                result.return_code,
                result.failure_kind.value,
                result.stdout_bytes or len(result.stdout.encode("utf-8", errors="replace")),
                result.stderr_bytes or len(result.stderr.encode("utf-8", errors="replace")),
                profile_digest=self._profile_digest,
                stdout_digest=_digest(result.stdout),
                stderr_digest=_digest(result.stderr),
            )
        )
        return result


__all__ = [
    "ObservedServerConnection",
    "ObservedServerFileTransfer",
]
