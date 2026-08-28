from __future__ import annotations

from research_platform.participant.method.runtime import InMemoryMethodObservationSink

from sem_test_support import build_self_evolving_memory_method

import unittest

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodServices
from projects.sem_paper.method.self_evolving_memory.session import SEMEvolutionPostCommitError, SEMEvolutionRecoveryRequired
from projects.sem_paper.method.self_evolving_memory.session_evolution_api import EvolutionReconciliation, EvolutionReconciliationStatus


class SEMEvolutionReconciliationV121Tests(unittest.TestCase):
    def _context(self):
        return ExecutionContext("run","trace","span",task_id="task",operation_id="op:done")

    def test_no_authoritative_adoption_resolves_uncertain_without_replaying_evolution(self):
        calls=[]
        class Controller:
            def on_task_completed(self,context): calls.append("run"); raise OSError("cut")
            def reconcile_uncertain(self,**kwargs):
                calls.append("reconcile")
                return EvolutionReconciliation(
                    EvolutionReconciliationStatus.NO_AUTHORITATIVE_ADOPTION,
                    authoritative_generation=kwargs["base_generation"],
                )
        class Factory:
            def __call__(self,source): return Controller()
        session=build_self_evolving_memory_method(evolution_factory=Factory(),evolution_provider_id="test.reconcile.none.v1").open_session(
            session_id="s",services=MethodServices(InMemoryMethodObservationSink())
        )
        ctx=self._context()
        with self.assertRaises(SEMEvolutionPostCommitError): session.task_completed({},ctx)
        task_key="task:run:task"
        result=session.reconcile_task(task_key,ctx)
        self.assertEqual(result.status,EvolutionReconciliationStatus.NO_AUTHORITATIVE_ADOPTION)
        session.task_completed({},ctx)
        self.assertEqual(calls,["run","reconcile"])
        self.assertEqual(session.diagnostics()["tasks_completed"],1)
        self.assertEqual(session.diagnostics()["task_terminal_reason_counts"],{"evolution_failed_no_authoritative_adoption":1})

    def test_confirmed_adoption_syncs_generation_without_rerunning_evolution(self):
        class Controller:
            def on_task_completed(self,context): raise OSError("return path cut")
            def reconcile_uncertain(self,**kwargs):
                return EvolutionReconciliation(
                    EvolutionReconciliationStatus.ADOPTION_CONFIRMED,
                    authoritative_generation="g_confirmed",
                )
        class Factory:
            def __call__(self,source): return Controller()
        sink=InMemoryMethodObservationSink()
        session=build_self_evolving_memory_method(evolution_factory=Factory(),evolution_provider_id="test.reconcile.adopt.v1").open_session(
            session_id="s",services=MethodServices(sink)
        )
        ctx=self._context()
        with self.assertRaises(SEMEvolutionPostCommitError): session.task_completed({},ctx)
        session.reconcile_task("task:run:task",ctx)
        self.assertEqual(session.diagnostics()["generation"],"g_confirmed")
        self.assertEqual([x.payload["mutation_type"] for x in sink.rows()],["TASK_COMPLETED","ADOPTION_SYNC"])

    def test_unresolved_reconciliation_keeps_blind_retry_blocked(self):
        class Controller:
            def on_task_completed(self,context): raise OSError("cut")
            def reconcile_uncertain(self,**kwargs):
                return EvolutionReconciliation(EvolutionReconciliationStatus.UNRESOLVED,reason="ambiguous")
        class Factory:
            def __call__(self,source): return Controller()
        session=build_self_evolving_memory_method(evolution_factory=Factory(),evolution_provider_id="test.reconcile.unresolved.v1").open_session(
            session_id="s",services=MethodServices(InMemoryMethodObservationSink())
        )
        ctx=self._context()
        with self.assertRaises(SEMEvolutionPostCommitError): session.task_completed({},ctx)
        with self.assertRaises(SEMEvolutionRecoveryRequired): session.reconcile_task("task:run:task",ctx)
        with self.assertRaises(SEMEvolutionRecoveryRequired): session.task_completed({},ctx)


if __name__ == "__main__": unittest.main()
