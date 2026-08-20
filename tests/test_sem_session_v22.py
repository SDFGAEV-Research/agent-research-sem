from tests_support import build_fixed_memory_method, build_self_evolving_memory_method
from research_platform.participant.method.runtime import (
    DefaultMethodObservationOutboxFactory,
    InMemoryMethodObservationSink,
)
from tests_support import build_fixed_memory_method
import json
import threading
import unittest
from dataclasses import replace

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import RecallRequest, MethodObservationDeliveryError, MethodRuntimeIdentity, MethodServices
from projects.sem_paper.method.self_evolving_memory import SelfEvolvingMemoryRuntime
from projects.sem_paper.method.self_evolving_memory.session_state_memory import InMemorySEMSessionStateFactory


class SEMSessionV22Tests(unittest.TestCase):
    @staticmethod
    def _services():
        return MethodServices(InMemoryMethodObservationSink())

    def test_snapshot_roundtrip_is_hash_verified_session_bound_and_restores_jmem(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('r','t','s')
        s=method.open_session(session_id='s1',services=self._services())
        s.ingest({'x':1},ctx); s.ingest({'x':2},ctx); s.task_completed({},ctx)
        before=s.diagnostics(); snap=s.checkpoint()
        other=method.open_session(session_id='s1',services=self._services()); other.restore(snap); after=other.diagnostics()
        self.assertEqual(after['evidence_sequence'],2)
        self.assertEqual(after['tasks_completed'],1)
        self.assertEqual(after['snapshot_schema'],'8')
        self.assertEqual(after['evidence_digest'],before['evidence_digest'])
        other.ingest({'x':3},ctx)
        self.assertEqual(other.diagnostics()['evidence_sequence'],3)
        wrong=method.open_session(session_id='s2',services=self._services())
        with self.assertRaises(ValueError): wrong.restore(snap)

    def test_non_current_schema_is_intentionally_rejected(self):
        method=build_fixed_memory_method(); s=method.open_session(session_id='s1',services=self._services()); snap=s.checkpoint()
        with self.assertRaises(ValueError): s.restore(replace(snap,schema_version='5'))

    def test_snapshot_is_bound_to_method_runtime_identity(self):
        source=build_fixed_memory_method()
        session=source.open_session(session_id='s',services=self._services())
        snap=session.checkpoint()

        class AlternateRuntime(SelfEvolvingMemoryRuntime):
            @property
            def runtime_identity(self):
                return MethodRuntimeIdentity("sem.session_runtime.alternate","1","abi1","a"*64)

        target=build_fixed_memory_method(
            runtime=AlternateRuntime(
                InMemorySEMSessionStateFactory(),
                DefaultMethodObservationOutboxFactory(),
            )
        )
        self.assertEqual(source.identity,target.identity)
        self.assertNotEqual(source.binding_digest,target.binding_digest)
        other=target.open_session(session_id='s',services=self._services())
        with self.assertRaises(ValueError):
            other.restore(snap)

    def test_session_state_backend_changes_runtime_identity_not_scientific_identity(self):
        base = build_fixed_memory_method()

        class AlternateStateFactory(InMemorySEMSessionStateFactory):
            BACKEND_ID = "sem.session_state.memory.alternate-test"

        alternate = build_fixed_memory_method(
            runtime=SelfEvolvingMemoryRuntime(
                AlternateStateFactory(),
                DefaultMethodObservationOutboxFactory(),
            )
        )
        self.assertEqual(base.identity, alternate.identity)
        self.assertNotEqual(base.runtime_identity, alternate.runtime_identity)
        self.assertNotEqual(base.binding_digest, alternate.binding_digest)

    def test_closed_session_fails_fast(self):
        method=build_fixed_memory_method(); s=method.open_session(session_id='s',services=self._services()); s.close()
        with self.assertRaises(RuntimeError): s.checkpoint()

    def test_non_json_evidence_fails_without_advancing_state(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('r','t','s'); s=method.open_session(session_id='s',services=self._services())
        with self.assertRaises(TypeError): s.ingest({'bad': object()},ctx)
        self.assertEqual(s.diagnostics()['evidence_sequence'],0)

    def test_tampered_nested_jmem_is_rejected_before_live_state_swap(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('r','t','s'); s=method.open_session(session_id='s',services=self._services()); s.ingest({'x':1},ctx)
        snap=s.checkpoint(); doc=json.loads(snap.opaque_payload); doc['evidence']['rows'][0]['payload']={'x':999}
        raw=json.dumps(doc,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        import hashlib
        tampered=replace(snap,opaque_payload=raw,payload_sha256=hashlib.sha256(raw).hexdigest())
        target=method.open_session(session_id='s',services=self._services())
        with self.assertRaises(ValueError): target.restore(tampered)
        self.assertEqual(target.diagnostics()['evidence_sequence'],0)

    def test_concurrent_ingest_has_contiguous_unique_sequence(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('r','t','s'); s=method.open_session(session_id='s',services=self._services())
        errors=[]
        def worker(i):
            try: s.ingest({'i':i},ctx)
            except Exception as exc: errors.append(exc)
        threads=[threading.Thread(target=worker,args=(i,)) for i in range(32)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors,[])
        self.assertEqual(s.diagnostics()['evidence_sequence'],32)

    def test_session_state_cell_revision_and_last_mutation_are_monotonic(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('r','t','s'); s=method.open_session(session_id='s',services=self._services())
        self.assertEqual(s.diagnostics()['revision'],0)
        s.ingest({'x':1},ctx)
        self.assertEqual((s.diagnostics()['revision'],s.diagnostics()['last_mutation']),(1,'INGEST'))
        s.task_completed({},ctx)
        self.assertEqual((s.diagnostics()['revision'],s.diagnostics()['last_mutation']),(2,'TASK_COMPLETED'))
        snap=s.checkpoint(); target=method.open_session(session_id='s',services=self._services()); target.restore(snap)
        self.assertEqual((target.diagnostics()['revision'],target.diagnostics()['last_mutation']),(3,'RESTORE'))

    def test_restore_into_mutated_live_session_never_moves_revision_backwards(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('r','t','s')
        source=method.open_session(session_id='s',services=self._services())
        source.ingest({'x':1},ctx)
        snap=source.checkpoint()

        target=method.open_session(session_id='s',services=self._services())
        for i in range(5):
            target.ingest({'live':i},ctx)
        self.assertEqual(target.diagnostics()['revision'],5)
        target.restore(snap)
        self.assertEqual(target.diagnostics()['revision'],6)
        self.assertEqual(target.diagnostics()['last_mutation'],'RESTORE')
        self.assertEqual(target.diagnostics()['evidence_sequence'],1)

    def test_mutation_lineage_records_context_and_digest_transitions(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('run','trace','span',task_id='task',decision_cycle_id='dc',operation_id='op')
        s=method.open_session(session_id='s',services=self._services())
        s.ingest({'b':2,'a':1},ctx)
        s.task_completed({},ctx)
        history=s.mutation_history()
        self.assertEqual([x.mutation_type for x in history],['INGEST','TASK_COMPLETED'])
        self.assertEqual(history[0].run_id,'run'); self.assertEqual(history[0].task_id,'task'); self.assertEqual(history[0].decision_cycle_id,'dc')
        self.assertNotEqual(history[0].before_state_digest,history[0].after_state_digest)
        self.assertNotEqual(history[0].before_evidence_digest,history[0].after_evidence_digest)
        self.assertEqual(history[1].before_evidence_digest,history[1].after_evidence_digest)
        self.assertEqual(s.recall(RecallRequest('anything',ctx)).context_text,'{"a":1,"b":2}')

    def test_snapshot_restore_preserves_mutation_tail_then_appends_restore(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('r','t','s')
        source=method.open_session(session_id='s',services=self._services()); source.ingest({'x':1},ctx); source.task_completed({},ctx)
        snap=source.checkpoint(); target=method.open_session(session_id='s',services=self._services()); target.restore(snap)
        history=target.mutation_history()
        self.assertEqual([x.mutation_type for x in history],['INGEST','TASK_COMPLETED','RESTORE'])
        self.assertEqual(history[-1].source_revision,2)

    def test_mutation_tail_is_bounded_without_breaking_monotonic_revision(self):
        method=build_fixed_memory_method(); ctx=ExecutionContext('r','t','s'); s=method.open_session(session_id='s',services=self._services())
        for i in range(80): s.ingest({'i':i},ctx)
        history=s.mutation_history(limit=1000)
        self.assertEqual(len(history),64)
        self.assertEqual(history[0].revision,17); self.assertEqual(history[-1].revision,80)

    def test_method_services_are_required_and_observation_failure_is_not_silent(self):
        method=build_fixed_memory_method()
        with self.assertRaises(TypeError):
            method.open_session(session_id='s',services=object())
        class Broken:
            def record(self, observation): raise OSError('telemetry down')
        s=method.open_session(session_id='s',services=MethodServices(Broken()))
        with self.assertRaises(MethodObservationDeliveryError) as cm:
            s.ingest({'x':1},ExecutionContext('r','t','s'))
        self.assertTrue(cm.exception.mutation_committed)
        self.assertEqual(s.diagnostics()['evidence_sequence'],1)
        self.assertEqual(s.diagnostics()['pending_observations'],1)

    def test_contextual_mutations_emit_method_observations(self):
        sink=InMemoryMethodObservationSink(); method=build_fixed_memory_method(); s=method.open_session(session_id='s',services=MethodServices(sink))
        ctx=ExecutionContext('r','t','s',task_id='task',decision_cycle_id='dc')
        s.ingest({'x':1},ctx); s.task_completed({},ctx); s.close()
        rows=sink.rows()
        self.assertEqual([r.payload['mutation_type'] for r in rows],['INGEST','TASK_COMPLETED','CLOSE'])
        self.assertEqual(rows[0].context.decision_cycle_id,'dc')
        self.assertEqual(rows[0].payload['revision'],1)

    def test_failed_observation_delivery_is_replayed_without_replaying_ingest(self):
        class FailOnce:
            def __init__(self): self.calls=0; self.rows=[]
            def record(self,o):
                self.calls+=1
                if self.calls==1: raise OSError('down')
                self.rows.append(o); return len(self.rows)
        sink=FailOnce(); s=build_fixed_memory_method().open_session(session_id='s',services=MethodServices(sink)); ctx=ExecutionContext('r','t','s')
        with self.assertRaises(MethodObservationDeliveryError): s.ingest({'x':1},ctx)
        self.assertEqual(s.diagnostics()['evidence_sequence'],1)
        delivered=s.flush_observations()
        self.assertEqual(len(delivered),1); self.assertEqual(s.diagnostics()['evidence_sequence'],1); self.assertEqual(s.diagnostics()['pending_observations'],0)

    def test_pending_observation_is_in_exact_snapshot(self):
        class Down:
            def record(self,o): raise OSError('down')
        source=build_fixed_memory_method().open_session(session_id='s',services=MethodServices(Down())); ctx=ExecutionContext('r','t','s')
        with self.assertRaises(MethodObservationDeliveryError): source.ingest({'x':1},ctx)
        snap=source.checkpoint()
        target=build_fixed_memory_method().open_session(session_id='s',services=MethodServices(InMemoryMethodObservationSink())); target.restore(snap)
        self.assertEqual(target.diagnostics()['pending_observations'],1)
        self.assertEqual(len(target.flush_observations()),1)

if __name__=='__main__': unittest.main()
