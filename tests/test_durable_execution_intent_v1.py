from pathlib import Path

from research_platform.execution.api import ExecutionOperationIntent
from research_platform.execution.command.api import ExecutionCommand
from research_platform.execution.command.providers import SQLiteCommandStore
from research_platform.execution.command.runtime import CommandIntentOwner
from research_platform.execution.operation.api import OperationId
from research_platform.execution.operation.providers import SQLiteOperationStore
from research_platform.execution.operation.runtime import OperationOwner
from research_platform.execution.runtime import ExecutionIntentCoordinator


class _FailOnceOperationSubmission:
    def __init__(self, delegate: OperationOwner) -> None:
        self.delegate = delegate
        self.failed = False

    def submit(self, *args, **kwargs):
        if not self.failed:
            self.failed = True
            raise RuntimeError("injected crash window after durable command")
        return self.delegate.submit(*args, **kwargs)


def _intent() -> ExecutionOperationIntent:
    command = ExecutionCommand.create(
        command_id="cmd:intent:1", command_type="environment.action", payload_schema="action.v1",
        payload_digest="a" * 64, deduplication_key="request:1", now_unix=10.0,
    )
    return ExecutionOperationIntent(command, OperationId("op:intent:1"))


def test_command_then_operation_crash_window_is_replayable(tmp_path: Path):
    command_path = tmp_path / "commands.sqlite3"
    operation_path = tmp_path / "operations.sqlite3"
    commands = CommandIntentOwner(SQLiteCommandStore(command_path))
    operations = OperationOwner(SQLiteOperationStore(operation_path))
    coordinator = ExecutionIntentCoordinator(commands, _FailOnceOperationSubmission(operations))

    try:
        coordinator.submit(_intent())
    except RuntimeError as exc:
        assert "injected crash window" in str(exc)
    else:
        raise AssertionError("fault injection must interrupt between durable authorities")

    assert commands.require(_intent().command.command_id) == _intent().command
    assert SQLiteOperationStore(operation_path).load(_intent().operation_id) is None

    restarted = ExecutionIntentCoordinator(
        CommandIntentOwner(SQLiteCommandStore(command_path)),
        OperationOwner(SQLiteOperationStore(operation_path)),
    )
    recovered = restarted.submit(_intent())
    assert not recovered.command_created
    assert recovered.operation_created
    assert recovered.operation.command_id == recovered.command.command_id
    replayed = restarted.submit(_intent())
    assert not replayed.command_created
    assert not replayed.operation_created
    assert replayed.command == recovered.command
    assert replayed.operation == recovered.operation
