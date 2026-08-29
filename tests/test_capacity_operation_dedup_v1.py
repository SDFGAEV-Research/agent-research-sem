from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from research_platform.execution.command.api import CommandId
from research_platform.execution.operation.api import OperationId
from research_platform.execution.operation.providers import SQLiteOperationStore
from research_platform.execution.operation.runtime import OperationOwner


def test_concurrent_same_operation_identity_creates_once(tmp_path: Path):
    path = tmp_path / "operations.sqlite3"
    SQLiteOperationStore(path)
    command_id = CommandId("cmd")
    operation_id = OperationId("op:stable")

    def submit(_: int):
        owner = OperationOwner(SQLiteOperationStore(path))
        return owner.submit(command_id, operation_id=operation_id, now_unix=1.0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(pool.map(submit, range(16)))
    operation_ids = {snapshot.operation_id.value for snapshot, _ in results}
    assert operation_ids == {operation_id.value}
    assert sum(1 for _, created in results if created) == 1
