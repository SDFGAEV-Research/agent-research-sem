from __future__ import annotations

from types import SimpleNamespace

from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from scripts.run_sem_minecraft_experiment import _paired_workload_id


def test_paired_workload_identity_is_shared_while_branch_identity_stays_external() -> None:
    control = _paired_workload_id(
        "run-1",
        role=BranchRole.CONTROL,
        branch=SimpleNamespace(branch_id="run-1:control"),
    )
    candidate = _paired_workload_id(
        "run-1",
        role=BranchRole.CANDIDATE,
        branch=SimpleNamespace(branch_id="run-1:candidate"),
    )

    assert control == candidate == "sem-paper:paired:run-1"
