from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from collections.abc import Iterator

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
        self._closed=False

    @contextmanager
    def _transaction(self) -> Iterator[object]:
        if self._closed:
            raise RuntimeError("forensic index write session is closed")
        conn = self.db.connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def project(self,bundle:ProjectionBundle,*,ledger:str,rows:int,tail_hash:str)->None:
        with self._lock, self._transaction() as conn:
            conn.execute(OBJECT_UPSERT_SQL,bundle.object.values)
            if bundle.state_writer is not None:
                conn.execute(STATE_UPSERT_SQL,bundle.state_writer.values)
            if bundle.operation_invocation is not None:
                conn.execute(OPERATION_INVOCATION_UPSERT_SQL, bundle.operation_invocation.values)
            conn.execute(FRESHNESS_UPSERT_SQL,(ledger,rows,tail_hash))

    def project_batch(
        self,
        bundles:tuple[ProjectionBundle,...],
        *,
        ledger:str,
        rows:int,
        tail_hash:str,
    )->None:
        with self._lock, self._transaction() as conn:
            conn.executemany(
                OBJECT_UPSERT_SQL,
                tuple(b.object.values for b in bundles),
            )
            state_rows=tuple(
                b.state_writer.values
                for b in bundles
                if b.state_writer is not None
            )
            if state_rows:
                conn.executemany(STATE_UPSERT_SQL,state_rows)
            operation_rows=tuple(
                b.operation_invocation.values
                for b in bundles
                if b.operation_invocation is not None
            )
            if operation_rows:
                conn.executemany(OPERATION_INVOCATION_UPSERT_SQL, operation_rows)
            conn.execute(FRESHNESS_UPSERT_SQL,(ledger,rows,tail_hash))

    def upsert(self,bundle:ProjectionBundle)->None:
        with self._lock, self._transaction() as conn:
            conn.execute(OBJECT_UPSERT_SQL,bundle.object.values)
            if bundle.state_writer is not None:
                conn.execute(STATE_UPSERT_SQL,bundle.state_writer.values)
            if bundle.operation_invocation is not None:
                conn.execute(OPERATION_INVOCATION_UPSERT_SQL, bundle.operation_invocation.values)

    def set_freshness(self,ledger:str,rows:int,tail_hash:str)->None:
        with self._lock, self._transaction() as conn:
            conn.execute(FRESHNESS_UPSERT_SQL,(ledger,rows,tail_hash))

    def close(self)->None:
        with self._lock:
            self._closed=True
