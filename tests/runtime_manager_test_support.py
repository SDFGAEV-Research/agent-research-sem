from __future__ import annotations

from pathlib import Path

from research_platform.execution.runtime.manager.history import RuntimeHistory
from research_platform.execution.runtime.manager.runtime_history_storage import FileRuntimeHistoryStorage
from research_platform.execution.runtime.manager.runtime_state_storage import FileRuntimeControlStateStore
from research_platform.execution.runtime.manager.state import RuntimeControlStore


def runtime_history_path(state_path: Path) -> Path:
    return state_path.with_name(state_path.name + ".history.jsonl")


def make_runtime_control_store(path: Path) -> RuntimeControlStore:
    return RuntimeControlStore(
        FileRuntimeControlStateStore(path),
        RuntimeHistory(FileRuntimeHistoryStorage(runtime_history_path(path))),
    )


__all__ = ["make_runtime_control_store", "runtime_history_path"]
