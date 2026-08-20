from __future__ import annotations

from threading import RLock

from research_platform.reliability.forensics.providers.index_db import ForensicIndexDB
from research_platform.reliability.forensics.providers.index_projection import ProjectionBundle
from research_platform.reliability.forensics.providers.index_sql import FRESHNESS_UPSERT_SQL, OBJECT_UPSERT_SQL, OPERATION_INVOCATION_UPSERT_SQL, STATE_UPSERT_SQL


class ForensicIndexWriteSession:
    """Owns one SQLite writer connection and all projection transactions."""

    def __init__(self,db:ForensicIndexDB)->None:
        if db.read_only:
            raise PermissionError("read-only forensic index cannot create write session")
        self.db=db
        self._lock=RLock()
        self._conn=db.connect()
        self._closed=False

    def project(self,bundle:ProjectionBundle,*,ledger:str,rows:int,tail_hash:str)->None:
        with self._lock,self._conn:
            self._conn.execute(OBJECT_UPSERT_SQL,bundle.object.values)
            if bundle.state_writer is not None:
                self._conn.execute(STATE_UPSERT_SQL,bundle.state_writer.values)
            if bundle.operation_invocation is not None:
                self._conn.execute(OPERATION_INVOCATION_UPSERT_SQL, bundle.operation_invocation.values)
            self._conn.execute(FRESHNESS_UPSERT_SQL,(ledger,rows,tail_hash))

    def project_batch(
        self,
        bundles:tuple[ProjectionBundle,...],
        *,
        ledger:str,
        rows:int,
        tail_hash:str,
    )->None:
        with self._lock,self._conn:
            self._conn.executemany(
                OBJECT_UPSERT_SQL,
                tuple(b.object.values for b in bundles),
            )
            state_rows=tuple(
                b.state_writer.values
                for b in bundles
                if b.state_writer is not None
            )
            if state_rows:
                self._conn.executemany(STATE_UPSERT_SQL,state_rows)
            operation_rows=tuple(
                b.operation_invocation.values
                for b in bundles
                if b.operation_invocation is not None
            )
            if operation_rows:
                self._conn.executemany(OPERATION_INVOCATION_UPSERT_SQL, operation_rows)
            self._conn.execute(FRESHNESS_UPSERT_SQL,(ledger,rows,tail_hash))

    def upsert(self,bundle:ProjectionBundle)->None:
        with self._lock,self._conn:
            self._conn.execute(OBJECT_UPSERT_SQL,bundle.object.values)
            if bundle.state_writer is not None:
                self._conn.execute(STATE_UPSERT_SQL,bundle.state_writer.values)
            if bundle.operation_invocation is not None:
                self._conn.execute(OPERATION_INVOCATION_UPSERT_SQL, bundle.operation_invocation.values)

    def set_freshness(self,ledger:str,rows:int,tail_hash:str)->None:
        with self._lock,self._conn:
            self._conn.execute(FRESHNESS_UPSERT_SQL,(ledger,rows,tail_hash))

    def close(self)->None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed=True
