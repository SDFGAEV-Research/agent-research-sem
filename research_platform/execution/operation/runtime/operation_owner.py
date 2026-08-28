from __future__ import annotations
import time
from research_platform.execution.command.api import CommandId
from research_platform.execution.operation.api import (EffectId,OperationEffectCertainty,OperationEffectProfile,OperationFailure,
    OperationFailureKind,OperationId,OperationSnapshot,OperationState,OperationStorePort,revise_operation,transition_operation)

class OperationOwner:
    """Single authority for operation identity, state and crash classification."""
    def __init__(self,store:OperationStorePort)->None: self._store=store
    @property
    def durability(self)->str: return self._store.durability
    def submit(self,command_id:CommandId,*,operation_id:OperationId,parent_operation_id:OperationId|None=None,
               effect_profile:OperationEffectProfile=OperationEffectProfile.NONE,effect_id:EffectId|None=None,
               now_unix:float|None=None)->tuple[OperationSnapshot,bool]:
        created_at=time.time() if now_unix is None else now_unix
        snapshot=OperationSnapshot(operation_id,command_id,OperationState.CREATED,0,created_at,created_at,
                                   parent_operation_id,effect_id,effect_profile)
        return self._store.create_or_get(snapshot)
    def require(self,operation_id:OperationId)->OperationSnapshot:
        snapshot=self._store.load(operation_id)
        if snapshot is None: raise KeyError(f"operation not found: {operation_id.value}")
        return snapshot
    def _transition_from(self,current:OperationSnapshot,target:OperationState,*,now_unix:float|None=None,**changes)->OperationSnapshot:
        updated=transition_operation(current,target,now_unix=now_unix,**changes)
        return self._store.compare_and_swap(current.version,updated)
    def _revise_from(self,current:OperationSnapshot,*,now_unix:float|None=None,**changes)->OperationSnapshot:
        updated=revise_operation(current,now_unix=now_unix,**changes)
        return self._store.compare_and_swap(current.version,updated)
    def queue(self,operation_id:OperationId,*,now_unix:float|None=None)->OperationSnapshot:
        return self._transition_from(self.require(operation_id),OperationState.QUEUED,now_unix=now_unix)
    def admit(self,operation_id:OperationId,*,now_unix:float|None=None)->OperationSnapshot:
        current=self.require(operation_id)
        if current.state not in {OperationState.CREATED,OperationState.QUEUED}:
            raise RuntimeError(f"operation is not admissible from state: {current.state.value}")
        return self._transition_from(current,OperationState.ADMITTED,now_unix=now_unix)
    def begin_execution(self,operation_id:OperationId)->OperationSnapshot:
        current=self.require(operation_id)
        if current.cancellation_requested:
            raise RuntimeError("cancelled operation cannot begin or resume execution")
        if current.state is OperationState.RECOVERING and current.effect_certainty is not OperationEffectCertainty.NOT_EXECUTED:
            raise RuntimeError("recovered external effect must be reconciled as not executed before retry")
        if current.state not in {OperationState.ADMITTED,OperationState.RECOVERING}:
            raise RuntimeError(f"operation is not executable from state: {current.state.value}")
        return self._transition_from(current,OperationState.RUNNING)
    def request_cancel(self,operation_id:OperationId,reason:str)->OperationSnapshot:
        reason=str(reason).strip()
        if not reason: raise ValueError("cancellation reason required")
        current=self.require(operation_id)
        if current.cancellation_requested:
            return current
        changes={"cancellation_requested":True,"cancellation_reason":reason}
        if current.state in {OperationState.CREATED,OperationState.QUEUED,OperationState.ADMITTED}:
            return self._transition_from(current,OperationState.CANCELLED,**changes)
        if current.state is OperationState.RUNNING:
            return self._transition_from(current,OperationState.CANCELLING,**changes)
        if current.state is OperationState.UNKNOWN_EFFECT:
            return self._revise_from(current,**changes)
        if current.state is OperationState.RECOVERING:
            if current.effect_certainty is OperationEffectCertainty.NOT_EXECUTED:
                return self._transition_from(current,OperationState.CANCELLED,**changes)
            return self._revise_from(current,**changes)
        raise RuntimeError(f"terminal operation cannot be cancelled from state: {current.state.value}")
    def mark_effect_unknown(self,operation_id:OperationId,*,failure:OperationFailure|None=None)->OperationSnapshot:
        current=self.require(operation_id)
        if current.effect_profile is OperationEffectProfile.NONE or current.effect_id is None:
            raise RuntimeError("effect-free operation cannot enter UNKNOWN_EFFECT")
        if failure is None:
            failure=OperationFailure(OperationFailureKind.EXTERNAL_EFFECT_UNCERTAIN,"EFFECT_UNCERTAIN",
                                     "external effect may have occurred; reconciliation required",False,True)
        return self._transition_from(current,OperationState.UNKNOWN_EFFECT,
                                     effect_certainty=OperationEffectCertainty.UNKNOWN,failure=failure)
    def recover_interrupted(self,operation_id:OperationId)->OperationSnapshot:
        current=self.require(operation_id)
        if current.state not in {OperationState.RUNNING,OperationState.CANCELLING}: return current
        if current.effect_profile is not OperationEffectProfile.NONE:
            return self.mark_effect_unknown(operation_id)
        if current.state is OperationState.CANCELLING:
            return self._transition_from(current,OperationState.CANCELLED,
                                         cancellation_reason=current.cancellation_reason or "cancelled during recovery")
        return self._transition_from(current,OperationState.RECOVERING)
    def reconcile_effect(self,operation_id:OperationId,certainty:OperationEffectCertainty)->OperationSnapshot:
        if certainty is OperationEffectCertainty.UNKNOWN:
            raise ValueError("reconciliation must resolve effect certainty")
        current=self.require(operation_id)
        if current.state is not OperationState.UNKNOWN_EFFECT:
            raise RuntimeError(f"operation does not require effect reconciliation: {current.state.value}")
        if current.cancellation_requested and certainty is OperationEffectCertainty.NOT_EXECUTED:
            return self._transition_from(
                current,OperationState.CANCELLED,effect_certainty=certainty,failure=None
            )
        return self._transition_from(
            current,OperationState.RECOVERING,effect_certainty=certainty,failure=None
        )
    def complete(self,operation_id:OperationId,*,result_digest:str|None=None,effect_certainty:OperationEffectCertainty|None=None)->OperationSnapshot:
        current=self.require(operation_id)
        certainty=effect_certainty
        if current.effect_profile is OperationEffectProfile.NONE:
            if certainty not in {None,OperationEffectCertainty.NOT_EXECUTED}:
                raise ValueError("effect-free operation cannot complete with external effect certainty")
            certainty=OperationEffectCertainty.NOT_EXECUTED
        elif certainty is None:
            if current.state is OperationState.RECOVERING and current.effect_certainty is OperationEffectCertainty.EXECUTED:
                certainty=OperationEffectCertainty.EXECUTED
            else:
                raise ValueError("effectful operation completion requires resolved effect certainty")
        if certainty is OperationEffectCertainty.UNKNOWN:
            raise ValueError("operation cannot complete with unknown effect certainty")
        return self._transition_from(
            current,OperationState.COMPLETED,result_digest=result_digest,failure=None,
            effect_certainty=certainty
        )
    def fail(self,operation_id:OperationId,failure:OperationFailure)->OperationSnapshot:
        current=self.require(operation_id)
        return self._transition_from(current,OperationState.FAILED,failure=failure)

__all__=["OperationOwner"]
