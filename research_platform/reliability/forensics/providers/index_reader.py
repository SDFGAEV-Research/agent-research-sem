from __future__ import annotations

from contextlib import closing
import json
from research_platform.reliability.forensics.providers.index_db import ForensicIndexDB
from research_platform.reliability.forensics.providers.operation_index import operation_invocation as read_operation_invocation, operations_open_at as read_operations_open_at, unclosed_operations as read_unclosed_operations

class ForensicIndexReadSession:
    """One read connection for a compound diagnostic query."""
    def __init__(self,db:ForensicIndexDB)->None: self.db=db; self.conn=db.connect(); self._closed=False
    def freshness(self)->dict[str,tuple[int,str]]:
        rows=self.conn.execute("SELECT ledger,rows,tail_hash FROM ledger_freshness ORDER BY ledger").fetchall(); return {str(n):(int(c),str(t)) for n,c,t in rows}
    def locate(self,object_id:str)->dict[str,object]|None:
        row=self.conn.execute("SELECT payload_json FROM object_index WHERE object_id=?",(object_id,)).fetchone(); return json.loads(row[0]) if row else None
    def last_writer(self,run_id:str,state_name:str)->dict[str,object]|None:
        row=self.conn.execute("SELECT payload_json FROM state_writers WHERE run_id=? AND state_name=? ORDER BY timestamp DESC LIMIT 1",(run_id,state_name)).fetchone(); return json.loads(row[0]) if row else None
    def around(self,*,run_id:str,timestamp:float,seconds:float=30.0)->tuple[dict[str,object],...]:
        rows=self.conn.execute("SELECT payload_json FROM object_index WHERE run_id=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp",(run_id,timestamp-seconds,timestamp+seconds)).fetchall(); return tuple(json.loads(r[0]) for r in rows)
    def recent_state_writers(self,*,run_id:str,before:float,limit:int=12)->tuple[dict[str,object],...]:
        if limit<=0:return ()
        rows=self.conn.execute("SELECT payload_json FROM state_writers WHERE run_id=? AND timestamp<=? ORDER BY timestamp DESC LIMIT ?",(run_id,before,limit)).fetchall(); return tuple(json.loads(r[0]) for r in rows)
    def related_to(self,object_id:str,*,limit:int=100)->tuple[dict[str,object],...]:
        if limit<=0:return ()
        row=self.conn.execute("SELECT run_id,task_id,decision_cycle_id,trace_id,span_id FROM object_index WHERE object_id=?",(object_id,)).fetchone()
        if row is None:return ()
        run_id,task_id,dc_id,trace_id,span_id=row
        rows=self.conn.execute('''SELECT payload_json FROM object_index WHERE run_id=? AND (
          (? IS NOT NULL AND task_id=?) OR (? IS NOT NULL AND decision_cycle_id=?) OR
          (? IS NOT NULL AND trace_id=?) OR (? IS NOT NULL AND span_id=?) OR object_id=?)
          ORDER BY timestamp LIMIT ?''',(run_id,task_id,task_id,dc_id,dc_id,trace_id,trace_id,span_id,span_id,object_id,limit)).fetchall()
        return tuple(json.loads(r[0]) for r in rows)
    def operation_invocation(self,invocation_id:str)->dict[str,object]|None:
        return read_operation_invocation(self.conn,invocation_id)
    def unclosed_operations(self,*,run_id:str|None=None,limit:int=100)->tuple[dict[str,object],...]:
        return read_unclosed_operations(self.conn,run_id=run_id,limit=limit)
    def operations_open_at(self,*,run_id:str,timestamp:float,limit:int=100)->tuple[dict[str,object],...]:
        return read_operations_open_at(self.conn,run_id=run_id,timestamp=timestamp,limit=limit)
    def close(self)->None:
        if not self._closed:self.conn.close();self._closed=True
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()

class ForensicIndexReader:
    """Pure query model with one-shot methods plus explicit compound-query sessions."""
    def __init__(self,db:ForensicIndexDB)->None:self.db=db
    def session(self)->ForensicIndexReadSession:return ForensicIndexReadSession(self.db)
    def freshness(self):
        with self.session() as s:return s.freshness()
    def locate(self,object_id):
        with self.session() as s:return s.locate(object_id)
    def last_writer(self,run_id,state_name):
        with self.session() as s:return s.last_writer(run_id,state_name)
    def around(self,*,run_id,timestamp,seconds=30.0):
        with self.session() as s:return s.around(run_id=run_id,timestamp=timestamp,seconds=seconds)
    def recent_state_writers(self,*,run_id,before,limit=12):
        with self.session() as s:return s.recent_state_writers(run_id=run_id,before=before,limit=limit)
    def related_to(self,object_id,*,limit=100):
        with self.session() as s:return s.related_to(object_id,limit=limit)
    def operation_invocation(self,invocation_id):
        with self.session() as s:return s.operation_invocation(invocation_id)
    def unclosed_operations(self,*,run_id=None,limit=100):
        with self.session() as s:return s.unclosed_operations(run_id=run_id,limit=limit)
    def operations_open_at(self,*,run_id,timestamp,limit=100):
        with self.session() as s:return s.operations_open_at(run_id=run_id,timestamp=timestamp,limit=limit)
