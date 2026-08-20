from __future__ import annotations

from pathlib import Path
from threading import RLock

from .segment_writer import RawSegmentWriter


class RawSegmentPool:
    """Owns writer identity/lifecycle for all `(run_id, family)` raw segments."""

    def __init__(self,root:Path)->None:
        self.root=root
        self._lock=RLock()
        self._writers:dict[tuple[str,str],RawSegmentWriter]={}
        self._closed=False

    @staticmethod
    def target(root:Path,run_id:str,family:str)->Path:
        safe_family=family.replace("/","_").replace(".","_")
        return root/run_id/f"{safe_family}.jsonl"

    def get(self,run_id:str,family:str,schema_version:str)->RawSegmentWriter:
        key=(run_id,family)
        with self._lock:
            if self._closed:
                raise RuntimeError("raw segment pool is closed")
            writer=self._writers.get(key)
            if writer is None:
                writer=RawSegmentWriter(
                    self.target(self.root,run_id,family),family,schema_version,run_id
                )
                self._writers[key]=writer
            elif writer.schema_version!=schema_version:
                raise ValueError(
                    f"raw segment schema drift for {key}: {writer.schema_version} != {schema_version}"
                )
            return writer

    def lock_for(self,run_id:str,family:str):
        with self._lock:
            writer=self._writers.get((run_id,family))
            return writer.lock if writer is not None else self._lock

    def close(self)->None:
        with self._lock:
            if self._closed:
                return
            writers=tuple(self._writers.values())
            self._closed=True
        for writer in writers:
            writer.close()
