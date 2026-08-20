from __future__ import annotations

from research_platform.platform.kernel import ExecutionContext
from methods.self_evolving_memory.adoption_reconciliation import ConservativeAdoptionReconciliationPort
from methods.self_evolving_memory.session_evolution_api import EvolutionReconciliationStatus


class Authority:
    def __init__(self,generation): self.generation=generation
    def reconcile_committed_generation(self): return self.generation


def test_same_authoritative_generation_proves_no_adoption_commit():
    port=ConservativeAdoptionReconciliationPort(Authority("g0"))
    result=port.reconcile(task_key="task",base_generation="g0",context=ExecutionContext("r","t","s"))
    assert result.status is EvolutionReconciliationStatus.NO_AUTHORITATIVE_ADOPTION


def test_advanced_generation_is_not_falsely_attributed_to_uncertain_task():
    port=ConservativeAdoptionReconciliationPort(Authority("g1"))
    result=port.reconcile(task_key="task",base_generation="g0",context=ExecutionContext("r","t","s"))
    assert result.status is EvolutionReconciliationStatus.UNRESOLVED
    assert "no task correlation" in result.reason
