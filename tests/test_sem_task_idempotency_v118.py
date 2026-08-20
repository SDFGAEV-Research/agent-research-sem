from __future__ import annotations

from research_platform.participant.method.runtime import InMemoryMethodObservationSink

from tests_support import build_fixed_memory_method, build_self_evolving_memory_method

import unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodObservationDeliveryError, MethodServices
from methods.self_evolving_memory.session import SEMEvolutionPostCommitError, SEMEvolutionRecoveryRequired


class SEMTaskIdempotencyV118Tests(unittest.TestCase):
    def test_duplicate_completed_task_is_a_noop_for_scientific_state_and_evolution(self):
        calls=[]
        class Controller:
            def on_task_completed(self,context): calls.append(context.operation_id); return None
        class Factory:
            def __call__(self,source): return Controller()
        sink=InMemoryMethodObservationSink()
        session=build_self_evolving_memory_method(evolution_factory=Factory(),evolution_provider_id="test.once.v1").open_session(
            session_id="s",services=MethodServices(sink)
        )
        ctx=ExecutionContext("run","trace","span",task_id="task",decision_cycle_id="dc",operation_id="op:done")
        session.task_completed({},ctx)
        session.task_completed({},ctx)
        self.assertEqual(session.diagnostics()["tasks_completed"],1)
        self.assertEqual(calls,["op:done"])
        self.assertEqual([x.mutation_type for x in session.mutation_history()],["TASK_COMPLETED"])
        self.assertEqual(len(sink.rows()),1)

    def test_evolution_failure_after_task_commit_never_blindly_replays(self):
        calls=[]
        class Controller:
            def on_task_completed(self,context): calls.append(1); raise RuntimeError("meta transport cut")
        class Factory:
            def __call__(self,source): return Controller()
        session=build_self_evolving_memory_method(evolution_factory=Factory(),evolution_provider_id="test.uncertain.v1").open_session(
            session_id="s",services=MethodServices(InMemoryMethodObservationSink())
        )
        ctx=ExecutionContext("run","trace","span",task_id="task",decision_cycle_id="dc",operation_id="op:done")
        with self.assertRaises(SEMEvolutionPostCommitError) as first:
            session.task_completed({},ctx)
        self.assertTrue(first.exception.task_completion_committed)
        self.assertEqual(session.diagnostics()["tasks_completed"],1)
        with self.assertRaises(SEMEvolutionRecoveryRequired):
            session.task_completed({},ctx)
        self.assertEqual(calls,[1])
        self.assertEqual(session.diagnostics()["tasks_completed"],1)

    def test_task_completion_observation_failure_replays_outbox_without_replaying_mutation(self):
        class FailOnce:
            def __init__(self): self.calls=0; self.rows=[]
            def record(self,row):
                self.calls+=1
                if self.calls==1: raise OSError("sink down")
                self.rows.append(row); return len(self.rows)
        sink=FailOnce()
        session=build_fixed_memory_method().open_session(session_id="s",services=MethodServices(sink))
        ctx=ExecutionContext("run","trace","span",task_id="task",operation_id="op:done")
        with self.assertRaises(MethodObservationDeliveryError):
            session.task_completed({},ctx)
        self.assertEqual(session.diagnostics()["tasks_completed"],1)
        session.task_completed({},ctx)
        self.assertEqual(session.diagnostics()["tasks_completed"],1)
        self.assertEqual(len(sink.rows),1)

    def test_snapshot_restores_completed_task_idempotency_guard(self):
        services=MethodServices(InMemoryMethodObservationSink())
        method=build_fixed_memory_method(); ctx=ExecutionContext("run","trace","span",task_id="task",operation_id="op:done")
        source=method.open_session(session_id="s",services=services); source.task_completed({},ctx); snap=source.checkpoint()
        target=method.open_session(session_id="s",services=MethodServices(InMemoryMethodObservationSink())); target.restore(snap)
        target.task_completed({},ctx)
        self.assertEqual(target.diagnostics()["tasks_completed"],1)
        self.assertEqual(target.diagnostics()["snapshot_schema"],"8")


if __name__ == "__main__": unittest.main()
