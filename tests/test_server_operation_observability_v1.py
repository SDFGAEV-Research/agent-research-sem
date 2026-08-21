from __future__ import annotations

import json
from pathlib import Path

from research_platform.runtime.server.api import (
    ServerOperationFinished,
    ServerOperationKind,
    ServerOperationStarted,
    ServerOperationState,
)
from research_platform.runtime.server.providers import (
    ObservedServerConnection,
    ObservedServerFileTransfer,
)
from research_platform.runtime.server.runtime import (
    JsonlServerOperationJournal,
    ServerOperationJournalIntegrityError,
)
from research_platform.runtime.server.identity.api import (
    ServerCommandResult,
    ServerConnectionProfile,
    ServerFileTransferResult,
)


class FakeJournal:
    def __init__(self) -> None:
        self.started: list[ServerOperationStarted] = []
        self.finished: list[ServerOperationFinished] = []

    def record_started(self, event: ServerOperationStarted) -> None:
        self.started.append(event)

    def record_finished(self, event: ServerOperationFinished) -> None:
        self.finished.append(event)


class FakeConnection:
    profile = ServerConnectionProfile("sem-ubuntu", "research.example", 60320, "ubuntu")

    def execute(self, command: str, *, interactive: bool = False) -> ServerCommandResult:
        return ServerCommandResult(
            self.profile.server_id,
            command,
            0,
            "ok\n",
            "",
            duration_seconds=0.25,
            stdout_bytes=3,
        )

    def interactive_argv(self, command: str, *, allocate_tty: bool = False) -> tuple[str, ...]:
        return ("ssh", "-tt" if allocate_tty else "-T", command)

    def run_interactive(self, argv: tuple[str, ...]) -> int:
        assert argv[0] == "ssh"
        return 0


class FakeTransfer:
    profile = ServerConnectionProfile("sem-ubuntu", "research.example", 60320, "ubuntu")

    def upload(self, local_path: str, remote_path: str, *, interactive: bool = False) -> ServerFileTransferResult:
        return ServerFileTransferResult(
            self.profile.server_id,
            local_path,
            remote_path,
            0,
            "",
            "",
            duration_seconds=0.5,
        )


def test_observed_connection_records_correlation_without_raw_command() -> None:
    journal = FakeJournal()
    result = ObservedServerConnection(FakeConnection(), journal).execute(
        "printf 'private-looking payload'"
    )
    assert result.succeeded
    assert len(journal.started) == 1
    assert len(journal.finished) == 1
    assert journal.started[0].kind == ServerOperationKind.COMMAND
    assert journal.finished[0].state == ServerOperationState.SUCCEEDED
    assert journal.started[0].request_digest != "printf 'private-looking payload'"


def test_observed_transfer_records_failure_boundary(tmp_path: Path) -> None:
    local = tmp_path / "release.zip"
    local.write_bytes(b"release")
    journal = FakeJournal()
    result = ObservedServerFileTransfer(FakeTransfer(), journal).upload(
        str(local), "/data/releases/release.zip"
    )
    assert result.succeeded
    assert journal.started[0].kind == ServerOperationKind.FILE_UPLOAD
    assert journal.finished[0].return_code == 0


def test_observed_interactive_attach_is_journaled_without_owning_subprocess() -> None:
    journal = FakeJournal()
    result = ObservedServerConnection(FakeConnection(), journal).run_interactive(
        ("ssh", "-tt", "ubuntu@research.example", "tmux attach")
    )
    assert result == 0
    assert journal.started[0].kind == ServerOperationKind.INTERACTIVE_ATTACH
    assert journal.finished[0].state == ServerOperationState.SUCCEEDED


def test_jsonl_journal_is_replayable_and_durable(tmp_path: Path) -> None:
    path = tmp_path / "server-operations.jsonl"
    journal = JsonlServerOperationJournal(path)
    journal.record_started(ServerOperationStarted("op-1", "sem-ubuntu", ServerOperationKind.COMMAND, "a" * 64, 1.0, False))
    journal.record_finished(ServerOperationFinished("op-1", "sem-ubuntu", ServerOperationKind.COMMAND, "a" * 64, ServerOperationState.FAILED, 2.0, 1.0, 255, "remote_exit", 3, 4))
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows] == ["started", "finished"]
    assert rows[1]["failure_kind"] == "remote_exit"
    record = journal.read_operation("op-1")
    assert record is not None
    assert record.finished is not None
    assert not record.effect_uncertain
    assert journal.pending_operations() == ()
    assert journal.recent_operations(1)[0].operation_id == "op-1"


def test_jsonl_journal_exposes_unfinished_effect_as_reconciliation_required(tmp_path: Path) -> None:
    path = tmp_path / "server-operations.jsonl"
    journal = JsonlServerOperationJournal(path)
    journal.record_started(
        ServerOperationStarted("op-pending", "sem-ubuntu", ServerOperationKind.FILE_UPLOAD, "b" * 64, 1.0, False)
    )

    pending = journal.pending_operations()
    assert [record.operation_id for record in pending] == ["op-pending"]
    assert pending[0].state == ServerOperationState.STARTED
    assert pending[0].effect_uncertain


def test_jsonl_journal_fails_closed_on_corrupt_tail(tmp_path: Path) -> None:
    path = tmp_path / "server-operations.jsonl"
    path.write_text('{"event":"started"}\nnot-json\n', encoding="utf-8")
    journal = JsonlServerOperationJournal(path)
    try:
        journal.pending_operations()
    except ServerOperationJournalIntegrityError as exc:
        assert "line" in str(exc)
    else:
        raise AssertionError("corrupt server-operation ledger was accepted")
