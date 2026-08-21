from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

import pytest

from research_platform.runtime.server.api import (
    ServerOperationEffect,
    ServerOperationFinished,
    ServerOperationKind,
    ServerOperationStarted,
    ServerOperationState,
    ServerOperationResolved,
    ServerOperationResolution,
    ServerOperationReconciliationRequired,
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

    def mutation_lock(self, *, server_id: str):
        del server_id
        return nullcontext()

    def pending_operations(self, *, server_id=None):
        del server_id
        return ()


class FakeConnection:
    profile = ServerConnectionProfile("sem-ubuntu", "research.example", 60320, "ubuntu")

    def execute(self, command: str, *, interactive: bool = False, effect=None) -> ServerCommandResult:
        del effect
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

    def download(self, remote_path: str, local_path: str, *, interactive: bool = False) -> ServerFileTransferResult:
        return ServerFileTransferResult(
            self.profile.server_id,
            local_path,
            remote_path,
            0,
            "",
            "",
            duration_seconds=0.5,
        )


class FailedConnection(FakeConnection):
    def execute(self, command: str, *, interactive: bool = False, effect=None) -> ServerCommandResult:
        del interactive, effect
        return ServerCommandResult(self.profile.server_id, command, 23, "", "remote failed")


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


def test_observed_connection_normalizes_unclassified_nonzero_provider_result() -> None:
    journal = FakeJournal()
    result = ObservedServerConnection(FailedConnection(), journal).execute("false")
    assert not result.succeeded
    assert journal.finished[0].failure_kind == "remote_exit"


def test_observed_connection_persists_redacted_diagnostic_preview(tmp_path: Path) -> None:
    class SecretConnection(FakeConnection):
        def execute(self, command: str, *, interactive: bool = False, effect=None) -> ServerCommandResult:
            del interactive, effect
            return ServerCommandResult(
                self.profile.server_id,
                command,
                23,
                "password=hidden token=secret-value",
                "remote failure",
            )

    journal = JsonlServerOperationJournal(tmp_path / "server-operations.jsonl")
    result = ObservedServerConnection(SecretConnection(), journal).execute("false")
    assert not result.succeeded
    record = journal.recent_operations(1)[0]
    assert record.finished is not None
    assert "hidden" not in record.finished.stdout_preview
    assert "secret-value" not in record.finished.stdout_preview
    assert "<REDACTED>" in record.finished.stdout_preview


def test_observed_mutation_is_blocked_by_an_unreconciled_effect(tmp_path: Path) -> None:
    journal = JsonlServerOperationJournal(tmp_path / "server-operations.jsonl")
    journal.record_started(
        ServerOperationStarted(
            "op-pending",
            "sem-ubuntu",
            ServerOperationKind.FILE_UPLOAD,
            "b" * 64,
            1.0,
            False,
            effect=ServerOperationEffect.MUTATION,
        )
    )
    with pytest.raises(ServerOperationReconciliationRequired, match="op-pending"):
        ObservedServerConnection(FakeConnection(), journal).execute(
            "touch /srv/state",
            effect=ServerOperationEffect.MUTATION,
        )
    assert len(journal.recent_operations()) == 1


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


def test_observed_download_uses_the_same_operation_ledger(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    journal = FakeJournal()
    result = ObservedServerFileTransfer(FakeTransfer(), journal).download(
        "/data/results/result.json", str(target)
    )
    assert result.succeeded
    assert journal.started[0].kind == ServerOperationKind.FILE_DOWNLOAD
    assert journal.finished[0].state == ServerOperationState.SUCCEEDED


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
    journal.record_started(ServerOperationStarted("op-1", "sem-ubuntu", ServerOperationKind.COMMAND, "a" * 64, 1.0, False, effect=ServerOperationEffect.OBSERVATION))
    journal.record_finished(ServerOperationFinished("op-1", "sem-ubuntu", ServerOperationKind.COMMAND, "a" * 64, ServerOperationState.FAILED, 2.0, 1.0, 255, "remote_exit", 3, 4, effect=ServerOperationEffect.OBSERVATION))
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
        ServerOperationStarted("op-pending", "sem-ubuntu", ServerOperationKind.FILE_UPLOAD, "b" * 64, 1.0, False, effect=ServerOperationEffect.MUTATION)
    )

    pending = journal.pending_operations()
    assert [record.operation_id for record in pending] == ["op-pending"]
    assert pending[0].state == ServerOperationState.STARTED
    assert pending[0].effect_uncertain


def test_jsonl_journal_scopes_recovery_to_the_requested_server(tmp_path: Path) -> None:
    journal = JsonlServerOperationJournal(tmp_path / "server-operations.jsonl")
    for operation_id, server_id in (("op-a", "server-a"), ("op-b", "server-b")):
        journal.record_started(
            ServerOperationStarted(
                operation_id,
                server_id,
                ServerOperationKind.COMMAND,
                operation_id.ljust(64, "a"),
                1.0,
                False,
                effect=ServerOperationEffect.MUTATION,
            )
        )
    assert [record.operation_id for record in journal.pending_operations(server_id="server-a")] == ["op-a"]
    assert [record.operation_id for record in journal.pending_operations(server_id="server-b")] == ["op-b"]
    assert [record.operation_id for record in journal.recent_operations(server_id="server-a")] == ["op-a"]


def test_jsonl_mutation_lock_is_stable_per_server_and_separate_between_servers(tmp_path: Path) -> None:
    journal = JsonlServerOperationJournal(tmp_path / "server-operations.jsonl")
    first_a = journal.mutation_lock(server_id="server-a")
    second_a = journal.mutation_lock(server_id="server-a")
    lock_b = journal.mutation_lock(server_id="server-b")
    assert first_a.path == second_a.path
    assert first_a.path != lock_b.path


def test_jsonl_journal_requires_explicit_resolution_before_new_mutation(tmp_path: Path) -> None:
    path = tmp_path / "server-operations.jsonl"
    journal = JsonlServerOperationJournal(path)
    journal.record_started(
        ServerOperationStarted(
            "op-pending",
            "sem-ubuntu",
            ServerOperationKind.FILE_UPLOAD,
            "b" * 64,
            1.0,
            False,
            "profile",
            ServerOperationEffect.MUTATION,
        )
    )
    journal.record_resolved(
        ServerOperationResolved(
            "op-pending",
            "sem-ubuntu",
            ServerOperationKind.FILE_UPLOAD,
            "b" * 64,
            ServerOperationResolution.EFFECT_NOT_APPLIED,
            2.0,
            "remote-check:op-pending",
            "c" * 64,
            "profile",
        )
    )
    record = journal.read_operation("op-pending")
    assert record is not None
    assert record.resolution is not None
    assert not record.effect_uncertain
    assert journal.pending_operations() == ()


def test_finished_timeout_remains_effect_uncertain(tmp_path: Path) -> None:
    journal = JsonlServerOperationJournal(tmp_path / "server-operations.jsonl")
    journal.record_started(
        ServerOperationStarted(
            "op-timeout",
            "sem-ubuntu",
            ServerOperationKind.COMMAND,
            "d" * 64,
            1.0,
            False,
            effect=ServerOperationEffect.MUTATION,
        )
    )
    journal.record_finished(
        ServerOperationFinished(
            "op-timeout",
            "sem-ubuntu",
            ServerOperationKind.COMMAND,
            "d" * 64,
            ServerOperationState.TIMED_OUT,
            2.0,
            1.0,
            124,
            "timeout",
            0,
            0,
            effect=ServerOperationEffect.MUTATION,
        )
    )
    assert [record.operation_id for record in journal.pending_operations()] == ["op-timeout"]


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
