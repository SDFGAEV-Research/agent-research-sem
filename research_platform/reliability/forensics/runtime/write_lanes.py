from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Callable, Generic, TypeVar

from research_platform.observability.api import EventEnvelope
from research_platform.reliability.forensics.runtime.event_projection_buffer import EventProjectionBuffer

T=TypeVar("T")


class ForensicProjectionError(RuntimeError):
    def __init__(
        self,
        ledger: str,
        rows: int,
        tail_hash: str,
        cause: BaseException,
        *,
        new_record: bool | None = None,
    ) -> None:
        super().__init__(
            f"authoritative {ledger} append committed but disposable projection failed "
            f"at rows={rows} tail={tail_hash}: {type(cause).__name__}: {cause}"
        )
        self.ledger=ledger
        self.rows=rows
        self.tail_hash=tail_hash
        self.cause=cause
        self.new_record=new_record


class EventWriteLane:
    """High-throughput authoritative append + projection barrier coordination."""

    def __init__(self,ledger,index,*,batch_size:int)->None:
        self.ledger=ledger
        self._lock=RLock()
        self.buffer=EventProjectionBuffer(index,batch_size=batch_size)

    def _flush_locked(self)->None:
        if not self.buffer.backlog():
            return
        # Preserve the exact authoritative cut in the failure envelope.
        cursor=self.buffer.current_cursor()
        assert cursor is not None
        try:
            self.buffer.flush()
        except Exception as exc:
            raise ForensicProjectionError("events",cursor.position,cursor.source_digest,exc) from exc

    def append(self,event:EventEnvelope)->str:
        with self._lock:
            row_hash=self.ledger.append(event.to_dict())
            rows,tail=self.ledger.cached_tail
            if self.buffer.add(event,rows,tail):
                self._flush_locked()
            return row_hash

    def flush(self)->None:
        with self._lock:
            self._flush_locked()

    @contextmanager
    def critical_barrier(self):
        """Make all prior events query-visible before a critical failure/mutation."""
        with self._lock:
            self._flush_locked()
            yield

    def backlog(self)->int:
        with self._lock:
            return self.buffer.backlog()


class CriticalWriteLane(Generic[T]):
    """Synchronous authoritative + projection lane for failure or state mutation."""

    def __init__(self,ledger_name:str,ledger,projector:Callable[...,None])->None:
        self.ledger_name=ledger_name
        self.ledger=ledger
        self.projector=projector
        self._lock=RLock()

    def append(self,obj:T)->str:
        with self._lock:
            row_hash=self.ledger.append(obj.to_dict())
            rows,tail=self.ledger.cached_tail
            try:
                self.projector(obj,rows=rows,tail_hash=tail)
            except Exception as exc:
                raise ForensicProjectionError(self.ledger_name,rows,tail,exc,new_record=True) from exc
            return row_hash
