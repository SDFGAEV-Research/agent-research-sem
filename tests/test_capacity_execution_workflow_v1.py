from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from research_platform.execution.operation.api import OperationId
from research_platform.execution.workflow.api import (
    WorkflowGraph, WorkflowProgressConflict, WorkflowRunId, WorkflowStep,
)
from research_platform.execution.workflow.providers import SQLiteWorkflowProgressStore
from research_platform.execution.workflow.runtime import WorkflowProgressOwner


def test_concurrent_claim_of_same_step_has_one_winner(tmp_path: Path):
    path = tmp_path / "workflow.sqlite3"
    run_id = WorkflowRunId("wf:race")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))
    WorkflowProgressOwner(SQLiteWorkflowProgressStore(path)).start(run_id, graph)

    def claim(index: int) -> bool:
        owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(path))
        try:
            owner.claim(run_id, graph, "effect", OperationId(f"op:{index}"))
            return True
        except (RuntimeError, WorkflowProgressConflict):
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = tuple(pool.map(claim, range(16)))
    assert sum(outcomes) == 1
    final = WorkflowProgressOwner(SQLiteWorkflowProgressStore(path)).require(run_id)
    assert len(final.running) == 1


def test_claim_reads_durable_progress_once_before_cas(tmp_path: Path):
    store = SQLiteWorkflowProgressStore(tmp_path / "workflow-loads.sqlite3")
    owner = WorkflowProgressOwner(store)
    run_id = WorkflowRunId("wf:single-load")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))
    owner.start(run_id, graph)
    original_load = store.load
    calls = 0

    def counted_load(workflow_run_id):
        nonlocal calls
        calls += 1
        return original_load(workflow_run_id)

    store.load = counted_load  # type: ignore[method-assign]
    owner.claim(run_id, graph, "effect", OperationId("op:single-load"))
    assert calls == 1
