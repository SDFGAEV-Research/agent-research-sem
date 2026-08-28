from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import math
import re
import time

from research_platform.execution.command.api import CommandId

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class OperationState(StrEnum):
    CREATED="created"; QUEUED="queued"; ADMITTED="admitted"; RUNNING="running"; CANCELLING="cancelling"
    RECOVERING="recovering"; UNKNOWN_EFFECT="unknown_effect"; COMPLETED="completed"; FAILED="failed"; CANCELLED="cancelled"


class OperationEffectProfile(StrEnum):
    NONE="none"; IDEMPOTENT="idempotent"; RECONCILABLE="reconcilable"; NON_IDEMPOTENT="non_idempotent"


class OperationEffectCertainty(StrEnum):
    NOT_EXECUTED="not_executed"; EXECUTED="executed"; UNKNOWN="unknown"


class OperationFailureKind(StrEnum):
    ADMISSION_REJECTED="admission_rejected"; SCHEDULING_TIMEOUT="scheduling_timeout"
    CAPABILITY_UNAVAILABLE="capability_unavailable"; CAPABILITY_REVOKED="capability_revoked"
    OPERATION_FAILURE="operation_failure"; WORKFLOW_FAILURE="workflow_failure"; CANCELLATION="cancellation"
    EXTERNAL_EFFECT_UNCERTAIN="external_effect_uncertain"; DEPENDENCY_FAILURE="dependency_failure"
    RUNTIME_FAILURE="runtime_failure"; PERSISTENCE_FAILURE="persistence_failure"; RECOVERY_FAILURE="recovery_failure"


@dataclass(frozen=True, slots=True)
class OperationId:
    value: str
    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("operation_id must be text")
        value=self.value.strip()
        if not value: raise ValueError("operation_id required")
        object.__setattr__(self,"value",value)


@dataclass(frozen=True, slots=True)
class EffectId:
    value: str
    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("effect_id must be text")
        value=self.value.strip()
        if not value: raise ValueError("effect_id required")
        object.__setattr__(self,"value",value)


@dataclass(frozen=True, slots=True)
class OperationFailure:
    kind: OperationFailureKind
    code: str
    message: str
    retryable: bool=False
    reconciliation_required: bool=False
    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not isinstance(self.message, str):
            raise TypeError("operation failure code/message must be text")
        code = self.code.strip()
        message = self.message.strip()
        if not code or not message:
            raise ValueError("operation failure code/message required")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        if self.kind is OperationFailureKind.EXTERNAL_EFFECT_UNCERTAIN and not self.reconciliation_required:
            raise ValueError("uncertain external effect must require reconciliation")


@dataclass(frozen=True, slots=True)
class OperationSnapshot:
    operation_id: OperationId
    command_id: CommandId
    state: OperationState
    version: int
    created_at_unix: float
    updated_at_unix: float
    parent_operation_id: OperationId | None=None
    effect_id: EffectId | None=None
    effect_profile: OperationEffectProfile=OperationEffectProfile.NONE
    effect_certainty: OperationEffectCertainty=OperationEffectCertainty.NOT_EXECUTED
    result_digest: str | None=None
    failure: OperationFailure | None=None
    cancellation_requested: bool=False
    cancellation_reason: str | None=None

    def __post_init__(self) -> None:
        if self.version < 0:
            raise ValueError("operation version cannot be negative")
        if not math.isfinite(self.created_at_unix) or self.created_at_unix < 0:
            raise ValueError("operation created_at_unix must be finite and non-negative")
        if not math.isfinite(self.updated_at_unix) or self.updated_at_unix < self.created_at_unix:
            raise ValueError("operation updated_at_unix must be finite and not precede creation")
        if self.parent_operation_id == self.operation_id:
            raise ValueError("operation cannot be its own parent")
        if self.result_digest is not None:
            digest = str(self.result_digest).strip().lower()
            if not _SHA256.fullmatch(digest):
                raise ValueError("operation result_digest must be a SHA-256 hex digest")
            if self.state is not OperationState.COMPLETED:
                raise ValueError("operation result_digest is valid only for COMPLETED state")
            object.__setattr__(self, "result_digest", digest)
        if self.effect_profile is not OperationEffectProfile.NONE and self.effect_id is None:
            raise ValueError("effectful operation requires stable effect_id before execution")
        if self.effect_profile is OperationEffectProfile.NONE:
            if self.effect_id is not None:
                raise ValueError("effect-free operation cannot carry effect_id")
            if self.effect_certainty is not OperationEffectCertainty.NOT_EXECUTED:
                raise ValueError("effect-free operation must remain NOT_EXECUTED")
        if self.state is OperationState.UNKNOWN_EFFECT:
            if self.effect_certainty is not OperationEffectCertainty.UNKNOWN:
                raise ValueError("UNKNOWN_EFFECT requires UNKNOWN effect certainty")
            if self.failure is None or self.failure.kind is not OperationFailureKind.EXTERNAL_EFFECT_UNCERTAIN:
                raise ValueError("UNKNOWN_EFFECT requires uncertain-effect failure evidence")
        if self.effect_certainty is OperationEffectCertainty.UNKNOWN and self.state is not OperationState.UNKNOWN_EFFECT:
            raise ValueError("UNKNOWN effect certainty is valid only while reconciliation is required")
        if self.failure is not None and self.state not in {OperationState.FAILED,OperationState.UNKNOWN_EFFECT}:
            raise ValueError("operation failure evidence is valid only for FAILED/UNKNOWN_EFFECT states")
        if self.failure is not None and self.failure.kind is OperationFailureKind.EXTERNAL_EFFECT_UNCERTAIN:
            if self.state is not OperationState.UNKNOWN_EFFECT:
                raise ValueError("uncertain-effect failure cannot be stored as terminal FAILED state")
        if self.state is OperationState.COMPLETED and self.failure is not None: raise ValueError("completed operation cannot carry failure")
        if self.state is OperationState.FAILED and self.failure is None: raise ValueError("failed operation requires failure")
        if not isinstance(self.cancellation_requested, bool):
            raise TypeError("operation cancellation_requested must be bool")
        reason = None if self.cancellation_reason is None else str(self.cancellation_reason).strip()
        if self.cancellation_requested and not reason:
            raise ValueError("operation cancellation request requires reason")
        if not self.cancellation_requested and reason is not None:
            raise ValueError("operation cancellation reason requires cancellation_requested")
        if self.state in {OperationState.CANCELLING, OperationState.CANCELLED} and not self.cancellation_requested:
            raise ValueError("cancelling/cancelled operation requires durable cancellation intent")
        object.__setattr__(self, "cancellation_reason", reason)


TERMINAL_OPERATION_STATES=frozenset({OperationState.COMPLETED,OperationState.FAILED,OperationState.CANCELLED})
_ALLOWED={
    OperationState.CREATED:{OperationState.QUEUED,OperationState.ADMITTED,OperationState.CANCELLED,OperationState.FAILED},
    OperationState.QUEUED:{OperationState.ADMITTED,OperationState.CANCELLING,OperationState.CANCELLED,OperationState.FAILED},
    OperationState.ADMITTED:{OperationState.RUNNING,OperationState.CANCELLING,OperationState.CANCELLED,OperationState.FAILED},
    OperationState.RUNNING:{OperationState.CANCELLING,OperationState.COMPLETED,OperationState.FAILED,OperationState.UNKNOWN_EFFECT,OperationState.RECOVERING},
    OperationState.CANCELLING:{OperationState.CANCELLED,OperationState.COMPLETED,OperationState.FAILED,OperationState.UNKNOWN_EFFECT},
    OperationState.UNKNOWN_EFFECT:{OperationState.RECOVERING,OperationState.CANCELLED},
    OperationState.RECOVERING:{OperationState.RUNNING,OperationState.COMPLETED,OperationState.FAILED,OperationState.CANCELLED,OperationState.UNKNOWN_EFFECT},
}


class IllegalOperationTransition(RuntimeError): pass


def _resolved_update_time(snapshot: OperationSnapshot, now_unix: float | None) -> float:
    if now_unix is None:
        return max(snapshot.updated_at_unix, time.time())
    if not math.isfinite(now_unix) or now_unix < snapshot.updated_at_unix:
        raise ValueError("operation transition timestamp cannot move backwards")
    return now_unix


def revise_operation(snapshot: OperationSnapshot, *, now_unix: float | None=None, **changes) -> OperationSnapshot:
    return replace(snapshot, version=snapshot.version + 1,
                   updated_at_unix=_resolved_update_time(snapshot, now_unix), **changes)


def transition_operation(snapshot: OperationSnapshot,target: OperationState,*,now_unix: float|None=None,**changes)->OperationSnapshot:
    if target not in _ALLOWED.get(snapshot.state,set()):
        raise IllegalOperationTransition(f"illegal operation transition: {snapshot.state.value} -> {target.value}")
    return replace(snapshot,state=target,version=snapshot.version+1,
                   updated_at_unix=_resolved_update_time(snapshot, now_unix),**changes)


__all__=["EffectId","IllegalOperationTransition","OperationEffectCertainty","OperationEffectProfile","OperationFailure",
         "OperationFailureKind","OperationId","OperationSnapshot","OperationState","TERMINAL_OPERATION_STATES",
         "revise_operation","transition_operation"]
