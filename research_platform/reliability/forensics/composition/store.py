from __future__ import annotations
from pathlib import Path

from research_platform.observability.api import EventEnvelope
from research_platform.reliability.failure.api import FailureEnvelope
from research_platform.reliability.forensics.api.mutation import MutationRecord
from research_platform.reliability.forensics.composition.runtime_factory import bootstrap_projection_freshness, build_forensic_runtime_parts
from research_platform.reliability.forensics.runtime.runtime_bundle import ForensicRuntimeBundle
from research_platform.reliability.forensics.runtime.runtime_lifecycle import ForensicRuntimeLifecycle
from research_platform.reliability.forensics.runtime.write_lanes import ForensicProjectionError


class ForensicStore:
    """Thin forensic façade; mutable resource ownership lives in ForensicRuntimeBundle."""

    EVENT_PROJECTION_BATCH=32

    def __init__(self,root:Path,*,read_only:bool=False):
        self.root=root
        self.read_only=read_only
        parts = build_forensic_runtime_parts(
            root,
            read_only=read_only,
            event_projection_batch=self.EVENT_PROJECTION_BATCH,
        )
        self._runtime = ForensicRuntimeBundle(
            root, read_only, parts, ForensicRuntimeLifecycle(parts)
        )
        if not read_only:
            bootstrap_projection_freshness(parts)
            parts.index.set_read_barrier(self._runtime.flush_projections)

    @property
    def failures(self): return self._runtime.failures
    @property
    def events(self): return self._runtime.events
    @property
    def mutations(self): return self._runtime.mutations
    @property
    def index(self): return self._runtime.index

    def _require_write(self)->None:
        self._runtime.require_write()

    @property
    def event_lane(self):
        self._require_write()
        assert self._runtime.event_lane is not None
        return self._runtime.event_lane

    def append_event(self,event:EventEnvelope)->str:
        return self.event_lane.append(event)

    def _append_critical(self,lane,obj)->str:
        self._require_write()
        with self.event_lane.critical_barrier():
            return lane.append(obj)

    def append_failure(self,failure:FailureEnvelope)->str:
        self._require_write()
        assert self._runtime.failure_lane is not None
        return self._append_critical(self._runtime.failure_lane,failure)

    def append_failure_once(self,failure:FailureEnvelope)->tuple[bool,str|None]:
        return self._runtime.append_failure_once(failure)

    def append_mutation(self,mutation:MutationRecord)->str:
        self._require_write()
        assert self._runtime.mutation_lane is not None
        return self._append_critical(self._runtime.mutation_lane,mutation)

    def flush_projections(self)->None:
        self._runtime.flush_projections()

    def projection_backlog(self)->int:
        return self._runtime.projection_backlog()

    def verify_all(self)->dict[str,tuple[int,str]]:
        return self._runtime.verify_all()

    def index_freshness(self)->tuple[bool,dict[str,tuple[int,str]],dict[str,tuple[int,str]]]:
        if not self.read_only:
            self.flush_projections()
        ledgers=self.verify_all()
        indexed=self.index.freshness()
        return ledgers==indexed,ledgers,indexed

    def close(self)->None:
        self._runtime.close()

    def __enter__(self):
        return self

    def __exit__(self,*exc):
        self.close()


__all__=["ForensicStore","ForensicProjectionError"]
