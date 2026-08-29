from pathlib import Path
import sqlite3

import pytest

from research_platform.execution.operation.api import OperationId
from research_platform.execution.workflow.api import (
    WorkflowGraph,
    WorkflowOperationBinding,
    WorkflowProgress,
    WorkflowProgressConflict,
    WorkflowProgressCorruption,
    WorkflowReconciliationProof,
    WorkflowRecoveryDisposition,
    WorkflowRunId,
    WorkflowStep,
)
from research_platform.execution.workflow.providers import SQLiteWorkflowProgressStore
from research_platform.execution.workflow.runtime import WorkflowProgressOwner




def _proof(run_id: WorkflowRunId, step_id: str, operation_id: OperationId, disposition: WorkflowRecoveryDisposition) -> WorkflowReconciliationProof:
    return WorkflowReconciliationProof(
        run_id, step_id, operation_id, disposition, "f" * 64, "test.workflow.reconciler"
    )


def _graph():
    return WorkflowGraph((
        WorkflowStep("prepare", "prepare"),
        WorkflowStep("effect", "effect", ("prepare",)),
    ))


def test_workflow_resume_marks_inflight_step_uncertain_until_reconciled(tmp_path: Path):
    path = tmp_path / "workflow.sqlite3"
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(path))
    run_id = WorkflowRunId("wf:1")
    owner.start(run_id, _graph())
    operation_id = OperationId("op:prepare")
    owner.claim(run_id, _graph(), "prepare", operation_id)

    restarted = WorkflowProgressOwner(SQLiteWorkflowProgressStore(path))
    recovered = restarted.recover_interrupted(run_id)
    assert not recovered.running
    assert recovered.uncertain[0].operation_id == operation_id
    assert restarted.ready_steps(run_id, _graph()) == ()

    reconciled = restarted.reconcile(_proof(run_id, "prepare", operation_id, WorkflowRecoveryDisposition.RETRY_NOT_EXECUTED))
    assert not reconciled.uncertain
    assert restarted.ready_steps(run_id, _graph()) == ("prepare",)


def test_workflow_reconciled_completion_preserves_operation_ancestry(tmp_path: Path):
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / "workflow.sqlite3"))
    run_id = WorkflowRunId("wf:2")
    operation_id = OperationId("op:prepare")
    owner.start(run_id, _graph())
    owner.claim(run_id, _graph(), "prepare", operation_id)
    owner.recover_interrupted(run_id)
    progress = owner.reconcile(_proof(run_id, "prepare", operation_id, WorkflowRecoveryDisposition.COMPLETED))
    assert progress.completed == (progress.completed[0],)
    assert progress.completed[0].operation_id == operation_id
    assert owner.ready_steps(run_id, _graph()) == ("effect",)


def test_workflow_cancel_returns_bound_operation_ids(tmp_path: Path):
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / "workflow.sqlite3"))
    run_id = WorkflowRunId("wf:3")
    graph = WorkflowGraph((WorkflowStep("a", "a"), WorkflowStep("b", "b")))
    owner.start(run_id, graph)
    owner.claim(run_id, graph, "a", OperationId("op:a"))
    owner.claim(run_id, graph, "b", OperationId("op:b"))
    progress, operations = owner.request_cancel(run_id, "user cancelled")
    assert progress.cancellation_requested
    assert {item.value for item in operations} == {"op:a", "op:b"}
    assert owner.ready_steps(run_id, graph) == ()


def test_workflow_store_rejects_corrupt_json_shape(tmp_path: Path):
    path = tmp_path / "workflow-corrupt.sqlite3"
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(path))
    run_id = WorkflowRunId("wf:corrupt")
    owner.start(run_id, _graph())
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE workflow_progress SET completed_json=? WHERE workflow_run_id=?",
            ('"prepare"', run_id.value),
        )
    try:
        SQLiteWorkflowProgressStore(path).load(run_id)
    except WorkflowProgressCorruption:
        pass
    else:
        raise AssertionError("corrupt workflow JSON shape must fail closed")


def test_stale_completion_cannot_complete_retried_step(tmp_path: Path):
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / "workflow-race.sqlite3"))
    run_id = WorkflowRunId("wf:stale-complete")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))
    old_operation = OperationId("op:old")
    new_operation = OperationId("op:new")
    owner.start(run_id, graph)
    owner.claim(run_id, graph, "effect", old_operation)
    owner.recover_interrupted(run_id)
    owner.reconcile(_proof(run_id, "effect", old_operation, WorkflowRecoveryDisposition.RETRY_NOT_EXECUTED))
    owner.claim(run_id, graph, "effect", new_operation)
    try:
        owner.complete(run_id, "effect", old_operation)
    except RuntimeError as exc:
        assert "stale workflow operation completion rejected" in str(exc)
    else:
        raise AssertionError("stale operation must not complete retried workflow step")

    completed = owner.complete(run_id, "effect", new_operation)
    assert completed.completed[0].operation_id == new_operation
    assert not completed.running


def test_stale_failure_cannot_fail_retried_step(tmp_path: Path):
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / "workflow-stale-fail.sqlite3"))
    run_id = WorkflowRunId("wf:stale-fail")
    graph = WorkflowGraph((WorkflowStep("effect", "effect"),))
    old_operation = OperationId("op:old")
    new_operation = OperationId("op:new")
    owner.start(run_id, graph)
    owner.claim(run_id, graph, "effect", old_operation)
    owner.recover_interrupted(run_id)
    owner.reconcile(_proof(run_id, "effect", old_operation, WorkflowRecoveryDisposition.RETRY_NOT_EXECUTED))
    owner.claim(run_id, graph, "effect", new_operation)
    try:
        owner.fail(run_id, "effect", old_operation)
    except RuntimeError as exc:
        assert "stale workflow operation completion rejected" in str(exc)
    else:
        raise AssertionError("stale operation must not fail retried workflow step")

    failed = owner.fail(run_id, "effect", new_operation)
    assert failed.failed is not None
    assert failed.failed.operation_id == new_operation
    assert not failed.running


def test_workflow_store_rejects_incompatible_existing_schema(tmp_path: Path):
    path = tmp_path / "workflow-old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE workflow_progress (workflow_run_id TEXT PRIMARY KEY)")
    try:
        SQLiteWorkflowProgressStore(path)
    except WorkflowProgressCorruption:
        pass
    else:
        raise AssertionError("incompatible workflow schema must fail closed")


def test_workflow_start_replay_preserves_existing_progress(tmp_path: Path):
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / "workflow-start-replay.sqlite3"))
    run_id = WorkflowRunId("wf:start-replay")
    graph = _graph()
    owner.start(run_id, graph)
    operation_id = OperationId("op:prepare")
    claimed = owner.claim(run_id, graph, "prepare", operation_id)

    replayed = owner.start(run_id, graph)
    assert replayed == claimed
    assert replayed.running[0].operation_id == operation_id


def test_workflow_start_rejects_graph_drift_for_existing_run(tmp_path: Path):
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / "workflow-start-drift.sqlite3"))
    run_id = WorkflowRunId("wf:start-drift")
    owner.start(run_id, _graph())
    different = WorkflowGraph((WorkflowStep("other", "other"),))
    try:
        owner.start(run_id, different)
    except ValueError as exc:
        assert "durable workflow identity" in str(exc)
    else:
        raise AssertionError("workflow run identity must not accept graph drift")


def test_workflow_first_failure_wins_and_replay_is_idempotent(tmp_path: Path):
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / "workflow-first-failure.sqlite3"))
    run_id = WorkflowRunId("wf:first-failure")
    graph = WorkflowGraph((WorkflowStep("a", "a"), WorkflowStep("b", "b")))
    op_a, op_b = OperationId("op:a"), OperationId("op:b")
    owner.start(run_id, graph)
    owner.claim(run_id, graph, "a", op_a)
    owner.claim(run_id, graph, "b", op_b)
    first = owner.fail(run_id, "a", op_a)
    assert first.failed is not None and first.failed.operation_id == op_a
    assert owner.fail(run_id, "a", op_a) == first
    try:
        owner.fail(run_id, "b", op_b)
    except RuntimeError as exc:
        assert "already failed" in str(exc)
    else:
        raise AssertionError("later parallel failure must not overwrite first workflow failure")
    persisted = owner.require(run_id)
    assert persisted.failed == first.failed
    assert persisted.running[0].operation_id == op_b


def test_workflow_store_rejects_nonempty_initial_progress(tmp_path: Path):
    store = SQLiteWorkflowProgressStore(tmp_path / "workflow-initial.sqlite3")
    run_id = WorkflowRunId("wf:invalid-initial")
    invalid = WorkflowProgress(
        run_id, "a" * 64, 1,
        running=(WorkflowOperationBinding("ghost", OperationId("op:ghost")),),
    )
    try:
        store.create(invalid)
    except WorkflowProgressConflict:
        pass
    else:
        raise AssertionError("workflow store must only create empty version-zero progress")


def test_workflow_store_cas_rejects_graph_drift_and_version_skip(tmp_path: Path):
    store = SQLiteWorkflowProgressStore(tmp_path / "workflow-cas.sqlite3")
    owner = WorkflowProgressOwner(store)
    run_id = WorkflowRunId("wf:cas")
    current = owner.start(run_id, _graph())
    drifted = WorkflowProgress(run_id, "b" * 64, 1)
    skipped = WorkflowProgress(run_id, current.graph_digest, 2)
    for candidate in (drifted, skipped):
        try:
            store.compare_and_swap(0, candidate)
        except WorkflowProgressConflict:
            pass
        else:
            raise AssertionError("workflow CAS must preserve identity and advance one version")


def test_workflow_reconciliation_rejects_bare_disposition_authority(tmp_path: Path) -> None:
    owner = WorkflowProgressOwner(SQLiteWorkflowProgressStore(tmp_path / "workflow-proof.sqlite3"))
    run_id = WorkflowRunId("wf:proof")
    operation_id = OperationId("op:proof")
    owner.start(run_id, _graph())
    owner.claim(run_id, _graph(), "prepare", operation_id)
    owner.recover_interrupted(run_id)
    with pytest.raises(TypeError, match="WorkflowReconciliationProof"):
        owner.reconcile(WorkflowRecoveryDisposition.COMPLETED)  # type: ignore[arg-type]
