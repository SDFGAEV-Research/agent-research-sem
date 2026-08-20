from __future__ import annotations

from threading import RLock

from research_platform.runtime.process.api import CaptureRotationReceipt, CaptureSyncReceipt, CaptureWriterState
from .fd import CaptureFD
from .state import CaptureStateCell
from .storage import CaptureStorage
from .tail import BoundedTail


class ActiveCaptureWriter:
    """Coordinates isolated fd, tail and counter authorities for one active stream."""

    def __init__(
        self,
        storage:CaptureStorage,
        *,
        max_segment_bytes:int,
        fsync_every_bytes:int,
        tail_bytes:int,
    )->None:
        self.storage=storage
        self.max_segment_bytes=max_segment_bytes
        self.fsync_every_bytes=fsync_every_bytes
        self.tail_bytes=tail_bytes
        self.lock=RLock()

        files=storage.files()
        total=storage.total_size()
        index=len(files)-1 if files else 0
        active_size=storage.active_size()
        self._state=CaptureStateCell(
            CaptureWriterState(index,total,0,storage.manifest_path.exists(),active_size)
        )
        self._tail=BoundedTail(tail_bytes,storage.load_tail(total,tail_bytes))
        self._fd=CaptureFD(storage.path(index))
        if not self.state.sealed:
            self._fd.open()

    @property
    def state(self)->CaptureWriterState:
        return self._state.value

    def _rotate(self)->CaptureRotationReceipt:
        old=self.state
        self._fd.close(sync=bool(old.since_sync))
        new=self._state.rotated()
        self._fd=CaptureFD(self.storage.path(new.index))
        self._fd.open()
        return CaptureRotationReceipt(old.index,new.index,new.total_bytes)

    def append(self,data:bytes)->tuple[CaptureRotationReceipt,...]:
        if not isinstance(data,(bytes,bytearray,memoryview)):
            raise TypeError("capture accepts bytes")
        if not data:
            return ()
        rotations=[]
        with self.lock:
            if self.state.sealed:
                raise RuntimeError("capture already sealed")
            view=memoryview(data); pos=0
            while pos<len(view):
                if self.state.active_size>=self.max_segment_bytes:
                    rotations.append(self._rotate())
                state=self.state
                n=min(len(view)-pos,self.max_segment_bytes-state.active_size)
                chunk=view[pos:pos+n]
                self._fd.write_all(chunk)
                self._tail.update(chunk)
                due=(state.since_sync+n)>=self.fsync_every_bytes
                if due:
                    self._fd.sync()
                self._state.appended(n,synced=due)
                pos+=n
            return tuple(rotations)

    def sync(self)->CaptureSyncReceipt:
        with self.lock:
            state=self.state
            if state.sealed:
                raise RuntimeError("capture already sealed")
            self._fd.sync()
            synced=state.since_sync
            self._state.synced()
            return CaptureSyncReceipt(
                self.storage.stream,
                state.index,
                state.total_bytes,
                synced,
                self._tail.sha256(),
            )

    def flush_active(self)->None:
        if not self.state.sealed:
            self._fd.sync()

    def tail(self,length:int|None=None)->bytes:
        with self.lock:
            return self._tail.read(length)

    def close_for_seal(self)->CaptureWriterState:
        state=self.state
        self._fd.close(sync=True)
        return state

    def mark_sealed(self,total_bytes:int)->None:
        self._state.sealed(total_bytes)

    def close(self)->None:
        with self.lock:
            self._fd.close(sync=bool(self.state.since_sync))
