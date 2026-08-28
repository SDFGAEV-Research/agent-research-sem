from research_platform.execution.command.api import ExecutionCommand
from research_platform.execution.operation.api import (
    EffectId, IllegalOperationTransition, OperationEffectCertainty, OperationEffectProfile, OperationFailure,
    OperationFailureKind, OperationId, OperationSnapshot, OperationState, transition_operation,
)

DIGEST = "a" * 64


def test_command_identity_is_distinct_from_operation_identity():
    command = ExecutionCommand.create(command_id="cmd-1", command_type="process.launch",
                                      payload_schema="launch.v1", payload_digest=DIGEST,
                                      deduplication_key="submit:1", now_unix=10.0)
    operation = OperationSnapshot(OperationId("op-1"), command.command_id, OperationState.CREATED, 0, 10.0, 10.0)
    assert command.command_id.value == "cmd-1"
    assert operation.operation_id.value == "op-1"


def test_terminal_operation_cannot_restart():
    current = OperationSnapshot(OperationId("op"), ExecutionCommand.create(
        command_id="cmd", command_type="x", payload_schema="x.v1", payload_digest=DIGEST,
        now_unix=1.0).command_id, OperationState.COMPLETED, 2, 1.0, 2.0)
    try:
        transition_operation(current, OperationState.RUNNING, now_unix=3.0)
    except IllegalOperationTransition:
        pass
    else:
        raise AssertionError("COMPLETED -> RUNNING must be rejected")


def test_unknown_effect_is_explicit_and_requires_reconciliation():
    command = ExecutionCommand.create(command_id="cmd", command_type="external.write",
                                      payload_schema="x.v1", payload_digest=DIGEST, now_unix=1.0)
    running = OperationSnapshot(OperationId("op"), command.command_id, OperationState.RUNNING, 3, 1.0, 2.0,
                                effect_id=EffectId("effect-1"), effect_profile=OperationEffectProfile.RECONCILABLE)
    failure = OperationFailure(OperationFailureKind.EXTERNAL_EFFECT_UNCERTAIN, "EFFECT_ACK_LOST",
                               "effect acknowledgement lost", retryable=False, reconciliation_required=True)
    unknown = transition_operation(running, OperationState.UNKNOWN_EFFECT, now_unix=3.0,
                                   effect_id=EffectId("effect-1"), effect_certainty=OperationEffectCertainty.UNKNOWN,
                                   failure=failure)
    assert unknown.state is OperationState.UNKNOWN_EFFECT
    assert unknown.effect_certainty is OperationEffectCertainty.UNKNOWN
    try:
        transition_operation(unknown, OperationState.RECOVERING, now_unix=4.0)
    except ValueError:
        pass
    else:
        raise AssertionError("UNKNOWN_EFFECT cannot leave reconciliation with unresolved certainty")


def test_operation_snapshot_rejects_contradictory_terminal_evidence():
    command = ExecutionCommand.create(command_id="cmd-x", command_type="x", payload_schema="x.v1",
                                      payload_digest=DIGEST, now_unix=1.0)
    try:
        OperationSnapshot(OperationId("op-x"), command.command_id, OperationState.RUNNING, 1, 1.0, 2.0,
                          result_digest="f" * 64)
    except ValueError:
        pass
    else:
        raise AssertionError("non-terminal operation cannot carry final result digest")


def test_uncertain_effect_failure_cannot_be_terminal_failed():
    command = ExecutionCommand.create(command_id="cmd-y", command_type="x", payload_schema="x.v1",
                                      payload_digest=DIGEST, now_unix=1.0)
    failure = OperationFailure(OperationFailureKind.EXTERNAL_EFFECT_UNCERTAIN, "ACK_LOST", "ack lost",
                               reconciliation_required=True)
    try:
        OperationSnapshot(OperationId("op-y"), command.command_id, OperationState.FAILED, 2, 1.0, 2.0,
                          effect_id=EffectId("effect-y"), effect_profile=OperationEffectProfile.RECONCILABLE,
                          failure=failure)
    except ValueError:
        pass
    else:
        raise AssertionError("uncertain effect cannot be collapsed into FAILED")


def test_operation_transition_rejects_backward_durable_timestamp():
    command = ExecutionCommand.create(command_id="cmd-z", command_type="x", payload_schema="x.v1",
                                      payload_digest=DIGEST, now_unix=1.0)
    current = OperationSnapshot(OperationId("op-z"), command.command_id, OperationState.CREATED, 0, 1.0, 5.0)
    try:
        transition_operation(current, OperationState.QUEUED, now_unix=4.0)
    except ValueError:
        pass
    else:
        raise AssertionError("durable operation timestamps must not move backwards")


def test_operation_cannot_be_its_own_parent():
    command = ExecutionCommand.create(command_id="cmd-p", command_type="x", payload_schema="x.v1",
                                      payload_digest=DIGEST, now_unix=1.0)
    operation_id = OperationId("op-p")
    try:
        OperationSnapshot(operation_id, command.command_id, OperationState.CREATED, 0, 1.0, 1.0,
                          parent_operation_id=operation_id)
    except ValueError:
        pass
    else:
        raise AssertionError("operation parent identity cannot self-reference")


def test_operation_and_effect_identity_do_not_coerce_non_text_values():
    for factory in (OperationId, EffectId):
        try:
            factory(123)  # type: ignore[arg-type]
        except TypeError:
            pass
        else:
            raise AssertionError("operation/effect identity must remain typed")
