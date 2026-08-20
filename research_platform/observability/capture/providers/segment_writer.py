from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from threading import RLock

from ..api.contracts import RawObservationReceipt
from .segment_recovery import recover_raw_segment


@dataclass(frozen=True, slots=True)
class SegmentWriterState:
    sequence:int
    closed:bool


class RawSegmentWriter:
    """Owns one append fd and lock; restart reconstruction lives elsewhere."""

    def __init__(self,target:Path,family:str,schema_version:str,run_id:str)->None:
        self.target=target; self.family=family; self.schema_version=schema_version; self.run_id=run_id
        self.lock=RLock()
        target.parent.mkdir(parents=True,exist_ok=True)
        recovered=recover_raw_segment(
            target,family=family,schema_version=schema_version,run_id=run_id
        )
        self.idempotency=recovered.idempotency
        self._state=SegmentWriterState(recovered.sequence,False)
        self._fd=os.open(target,os.O_CREAT|os.O_APPEND|os.O_WRONLY,0o644)

    @property
    def sequence(self)->int:
        return self._state.sequence

    @staticmethod
    def _write_all(fd:int,encoded:bytes)->None:
        view=memoryview(encoded); total=0
        while total<len(view):
            written=os.write(fd,view[total:])
            if written<=0:
                raise OSError("raw segment write returned zero bytes")
            total+=written

    def previous(self,idempotency_key:str)->RawObservationReceipt|None:
        return self.idempotency.get(idempotency_key)

    def append(self,encoded:bytes,receipt:RawObservationReceipt,idempotency_key:str|None)->None:
        if self._state.closed:
            raise RuntimeError("raw segment writer is closed")
        self._write_all(self._fd,encoded)
        self._state=SegmentWriterState(receipt.sequence,False)
        if idempotency_key is not None:
            self.idempotency[idempotency_key]=receipt

    def close(self)->None:
        with self.lock:
            if self._state.closed:
                return
            os.close(self._fd)
            self._state=SegmentWriterState(self._state.sequence,True)
