from pathlib import Path
import sqlite3

from research_platform.execution.command.api import CommandId
from research_platform.execution.operation.api import (
    EffectId, OperationConflict, OperationCorruption, OperationEffectCertainty, OperationEffectProfile,
    OperationFailure, OperationFailureKind, OperationId, OperationState,
)
from research_platform.execution.operation.providers import SQLiteOperationStore
from research_platform.execution.operation.runtime import OperationOwner


def _command_id(value: str = "cmd-1") -> CommandId:
    return CommandId(value)


def test_operation_reopens_and_replays_same_identity_after_restart(tmp_path: Path):
    path = tmp_path / "operations.sqlite3"
    first = OperationOwner(SQLiteOperationStore(path))
    created, is_new = first.submit(_command_id(), operation_id=OperationId("op-first"), now_unix=10.0)
    assert is_new and created.state is OperationState.CREATED
    queued = first.queue(created.operation_id, now_unix=11.0)
    second = OperationOwner(SQLiteOperationStore(path))
    replayed, is_new = second.submit(_command_id(), operation_id=OperationId("op-first"), now_unix=99.0)
    assert not is_new
    assert replayed.operation_id == queued.operation_id
    assert replayed.state is OperationState.QUEUED


def test_same_command_can_own_multiple_distinct_operations(tmp_path: Path):
    owner = OperationOwner(SQLiteOperationStore(tmp_path / "operations.sqlite3"))
    first, _ = owner.submit(_command_id(), operation_id=OperationId("op-1"), now_unix=10.0)
    second, _ = owner.submit(_command_id(), operation_id=OperationId("op-2"), now_unix=10.0)
    assert first.command_id == second.command_id
    assert first.operation_id != second.operation_id


def test_operation_identity_contract_drift_fails_closed(tmp_path: Path):
    owner = OperationOwner(SQLiteOperationStore(tmp_path / "operations.sqlite3"))
    owner.submit(_command_id("cmd-1"), operation_id=OperationId("op-1"), now_unix=10.0)
    try:
        owner.submit(_command_id("cmd-2"), operation_id=OperationId("op-1"), now_unix=10.0)
    except OperationConflict:
        pass
    else:
        raise AssertionError("operation identity reuse with different command must fail closed")


def _effectful_owner(tmp_path: Path, suffix: str):
    owner = OperationOwner(SQLiteOperationStore(tmp_path / f"{suffix}.sqlite3"))
    operation, _ = owner.submit(
        _command_id(f"cmd-{suffix}"),
        operation_id=OperationId(f"op-{suffix}"),
        effect_profile=OperationEffectProfile.RECONCILABLE,
        effect_id=EffectId(f"effect-{suffix}"),
        now_unix=10.0,
    )
    owner.admit(operation.operation_id, now_unix=11.0)
    owner.begin_execution(operation.operation_id)
    return owner, operation.operation_id


def test_uncertain_effect_cannot_blindly_enter_recovery(tmp_path: Path):
    owner, operation_id = _effectful_owner(tmp_path, "uncertain")
    owner.mark_effect_unknown(operation_id)
    assert not hasattr(owner, "begin_recovery")
    assert not hasattr(owner, "transition")
    try:
        owner.begin_execution(operation_id)
    except RuntimeError:
        pass
    else:
        raise AssertionError("uncertain external effect must reconcile before execution resumes")


def test_reconciliation_not_executed_allows_safe_retry(tmp_path: Path):
    owner, operation_id = _effectful_owner(tmp_path, "retry")
    owner.mark_effect_unknown(operation_id)
    recovered = owner.reconcile_effect(operation_id, OperationEffectCertainty.NOT_EXECUTED)
    assert recovered.state is OperationState.RECOVERING
    assert recovered.effect_certainty is OperationEffectCertainty.NOT_EXECUTED
    assert owner.begin_execution(operation_id).state is OperationState.RUNNING


def test_reconciliation_executed_blocks_reexecution_and_can_complete(tmp_path: Path):
    owner, operation_id = _effectful_owner(tmp_path, "executed")
    owner.mark_effect_unknown(operation_id)
    recovered = owner.reconcile_effect(operation_id, OperationEffectCertainty.EXECUTED)
    assert recovered.state is OperationState.RECOVERING
    try:
        owner.begin_execution(operation_id)
    except RuntimeError:
        pass
    else:
        raise AssertionError("confirmed external effect must not be re-executed")
    completed = owner.complete(operation_id, result_digest="d" * 64)
    assert completed.state is OperationState.COMPLETED
    assert completed.effect_certainty is OperationEffectCertainty.EXECUTED


def test_operation_store_rejects_partial_failure_corruption(tmp_path: Path):
    path = tmp_path / "operations-corrupt.sqlite3"
    owner = OperationOwner(SQLiteOperationStore(path))
    operation, _ = owner.submit(_command_id(), operation_id=OperationId("op-corrupt"), now_unix=10.0)
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE operations SET failure_code=? WHERE operation_id=?",
            ("ORPHAN_FAILURE_CODE", operation.operation_id.value),
        )
    try:
        SQLiteOperationStore(path).load(operation.operation_id)
    except OperationCorruption:
        pass
    else:
        raise AssertionError("partial operation failure columns must fail closed")


def test_cancelled_uncertain_effect_reconciles_not_executed_to_cancelled(tmp_path: Path):
    owner, operation_id = _effectful_owner(tmp_path, "cancel-not-executed")
    cancelling = owner.request_cancel(operation_id, "user cancelled")
    assert cancelling.state is OperationState.CANCELLING
    unknown = owner.recover_interrupted(operation_id)
    assert unknown.state is OperationState.UNKNOWN_EFFECT
    assert unknown.cancellation_requested
    assert unknown.cancellation_reason == "user cancelled"

    restarted = OperationOwner(SQLiteOperationStore(tmp_path / "cancel-not-executed.sqlite3"))
    persisted = restarted.require(operation_id)
    assert persisted.cancellation_requested
    cancelled = restarted.reconcile_effect(operation_id, OperationEffectCertainty.NOT_EXECUTED)
    assert cancelled.state is OperationState.CANCELLED
    assert cancelled.cancellation_reason == "user cancelled"


def test_cancelled_uncertain_effect_confirmed_executed_never_reexecutes(tmp_path: Path):
    owner, operation_id = _effectful_owner(tmp_path, "cancel-executed")
    owner.request_cancel(operation_id, "user cancelled")
    owner.recover_interrupted(operation_id)
    recovered = owner.reconcile_effect(operation_id, OperationEffectCertainty.EXECUTED)
    assert recovered.state is OperationState.RECOVERING
    assert recovered.cancellation_requested
    try:
        owner.begin_execution(operation_id)
    except RuntimeError:
        pass
    else:
        raise AssertionError("cancelled operation with confirmed effect must never re-execute")
    completed = owner.complete(operation_id, result_digest="e" * 64)
    assert completed.state is OperationState.COMPLETED
    assert completed.cancellation_requested
    assert completed.cancellation_reason == "user cancelled"


def test_failure_after_cancel_request_preserves_cancellation_evidence(tmp_path: Path):
    owner, operation_id = _effectful_owner(tmp_path, "cancel-fail")
    owner.request_cancel(operation_id, "operator stop")
    failure = OperationFailure(
        OperationFailureKind.OPERATION_FAILURE,
        "STOP_FAILED",
        "operation failed while cancellation was in progress",
    )
    failed = owner.fail(operation_id, failure)
    assert failed.state is OperationState.FAILED
    assert failed.cancellation_requested
    assert failed.cancellation_reason == "operator stop"


def test_old_operation_schema_is_rejected_instead_of_silently_upgraded(tmp_path: Path):
    path = tmp_path / "old-operation-schema.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE operations (
            operation_id TEXT PRIMARY KEY, command_id TEXT NOT NULL, state TEXT NOT NULL,
            version INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
            parent_operation_id TEXT, effect_id TEXT, effect_profile TEXT NOT NULL,
            effect_certainty TEXT NOT NULL, result_digest TEXT, failure_kind TEXT,
            failure_code TEXT, failure_message TEXT, failure_retryable INTEGER,
            failure_reconciliation_required INTEGER, cancellation_reason TEXT)""")
    try:
        SQLiteOperationStore(path)
    except OperationCorruption:
        pass
    else:
        raise AssertionError("obsolete durable schema must require an explicit migration")
