from __future__ import annotations

from pathlib import Path

from research_platform.reliability.forensics.providers.hashlog import HashChainedJSONL
from research_platform.reliability.forensics.providers.index import ForensicIndex
from research_platform.reliability.forensics.providers.lease import ForensicWriterLease
from research_platform.reliability.forensics.providers.segmented_hashlog import SegmentedHashChainedJSONL
from research_platform.reliability.forensics.api.runtime_parts import ForensicRuntimeParts
from research_platform.reliability.forensics.runtime.write_lanes import CriticalWriteLane, EventWriteLane


def build_forensic_runtime_parts(
    root:Path,
    *,
    read_only:bool,
    event_projection_batch:int,
)->ForensicRuntimeParts:
    """Construct runtime resources; no freshness/read-barrier bootstrap happens here."""

    lease=None
    if read_only:
        if not root.exists():
            raise FileNotFoundError(root)
    else:
        root.mkdir(parents=True,exist_ok=True)
        lease=ForensicWriterLease(root/".writer.lock").acquire()

    try:
        failures=HashChainedJSONL(root/"failures.chain.jsonl",fsync_every=1,read_only=read_only)
        events=SegmentedHashChainedJSONL(
            root/"events.chain",
            max_segment_bytes=8*1024*1024,
            fsync_every=32,
            read_only=read_only,
        )
        mutations=HashChainedJSONL(root/"mutations.chain.jsonl",fsync_every=1,read_only=read_only)
        index=ForensicIndex(root/"index.sqlite3",read_only=read_only)
        event_lane=None if read_only else EventWriteLane(
            events,index,batch_size=event_projection_batch
        )
        failure_lane=None if read_only else CriticalWriteLane(
            "failures",failures,lambda obj,**kw:index.project_failure(obj,**kw)
        )
        mutation_lane=None if read_only else CriticalWriteLane(
            "mutations",mutations,lambda obj,**kw:index.project_mutation(obj,**kw)
        )
        return ForensicRuntimeParts(
            failures,events,mutations,index,
            event_lane,failure_lane,mutation_lane,lease,
        )
    except Exception:
        if lease is not None:
            lease.release()
        raise


def bootstrap_projection_freshness(parts:ForensicRuntimeParts)->None:
    """Initialize only empty-ledger freshness markers for a writable runtime."""
    if parts.writer_lease is None:
        raise PermissionError("read-only forensic runtime cannot bootstrap projection freshness")
    existing=parts.index.freshness()
    for name,ledger in (
        ("failures",parts.failures),
        ("events",parts.events),
        ("mutations",parts.mutations),
    ):
        if name not in existing:
            count,tail=ledger.cached_tail
            if count==0:
                parts.index.set_freshness(name,count,tail)
