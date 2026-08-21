from __future__ import annotations

from dataclasses import dataclass

import pytest

from projects.sem_paper.composition.minecraft_branch import (
    MinecraftBranchExecutionError,
    MinecraftBranchExecutionResult,
    MinecraftPairedBranchRunner,
)
from projects.sem_paper.method.self_evolving_memory.evolution import (
    BranchRole,
    CandidateArchitecture,
    PrimitiveEdit,
    PrimitiveEditKind,
)
from research_platform.environment.minecraft.api import MinecraftWorldBranch, MinecraftWorldCut


def _cut() -> MinecraftWorldCut:
    return MinecraftWorldCut(
        "cut-1",
        "file:C:/snapshot/payload",
        "file:C:/snapshot/manifest.json",
        "world",
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "save:1",
    )


def _candidate() -> CandidateArchitecture:
    return CandidateArchitecture(
        "g1",
        "candidate-1",
        {"candidate": True},
        "d" * 64,
        (PrimitiveEdit(PrimitiveEditKind.CREATE, "n", {}),),
        ({"node_id": "n"},),
    )


@dataclass
class _WorldCuts:
    cut: MinecraftWorldCut
    materialized: list[tuple[str, str]]
    released: list[str]

    def capture(self, *, session_id, context):
        assert session_id == "session-1"
        return self.cut

    def materialize_branch(self, cut, *, branch_id, destination_workdir):
        assert cut is self.cut
        self.materialized.append((branch_id, destination_workdir))
        return MinecraftWorldBranch(
            branch_id,
            cut.cut_id,
            destination_workdir,
            cut.level_name,
            cut.manifest_digest,
            f"cleanup:{branch_id}",
        )

    def release_branch(self, branch):
        self.released.append(branch.branch_id)
        return branch.cleanup_ref


@dataclass
class _Executor:
    calls: list[tuple[BranchRole, CandidateArchitecture | None, str]]

    def execute(self, *, role, candidate, branch):
        self.calls.append((role, candidate, branch.cut_id))
        return MinecraftBranchExecutionResult(
            "workload-1",
            "environment-1",
            "tasks-1",
            (("utility", 1.0 if role is BranchRole.CANDIDATE else 0.5),),
        )


def test_paired_runner_requires_one_shared_source_cut_and_releases_each_branch() -> None:
    world_cuts = _WorldCuts(_cut(), [], [])
    executor = _Executor([])
    runner = MinecraftPairedBranchRunner(
        world_cuts=world_cuts,
        executor=executor,
        session_id="session-1",
        context=None,
        branch_id_factory=lambda role: f"branch-{role.value}",
        destination_factory=lambda branch_id: f"C:/branches/{branch_id}",
    )

    assert runner.prepare_source_cut().cut_id == "cut-1"
    control = runner.run(role=BranchRole.CONTROL, candidate=None)
    candidate = runner.run(role=BranchRole.CANDIDATE, candidate=_candidate())

    assert control.source_checkpoint_id == candidate.source_checkpoint_id == "cut-1"
    assert [item[2] for item in executor.calls] == ["cut-1", "cut-1"]
    assert world_cuts.released == ["branch-control", "branch-candidate"]


def test_paired_runner_does_not_implicitly_capture_a_new_cut() -> None:
    world_cuts = _WorldCuts(_cut(), [], [])
    runner = MinecraftPairedBranchRunner(
        world_cuts=world_cuts,
        executor=_Executor([]),
        session_id="session-1",
        context=None,
        branch_id_factory=lambda role: role.value,
        destination_factory=lambda branch_id: f"C:/branches/{branch_id}",
    )
    with pytest.raises(MinecraftBranchExecutionError) as caught:
        runner.run(role=BranchRole.CONTROL, candidate=None)
    assert caught.value.phase == "prepare"


def test_paired_runner_preserves_workload_and_cleanup_failures() -> None:
    world_cuts = _WorldCuts(_cut(), [], [])

    class FailingExecutor:
        def execute(self, *, role, candidate, branch):
            raise OSError("workload failed")

    def broken_release(branch):
        raise OSError("cleanup failed")

    world_cuts.release_branch = broken_release
    runner = MinecraftPairedBranchRunner(
        world_cuts=world_cuts,
        executor=FailingExecutor(),
        session_id="session-1",
        context=None,
        branch_id_factory=lambda role: role.value,
        destination_factory=lambda branch_id: f"C:/branches/{branch_id}",
    )
    runner.prepare_source_cut()
    with pytest.raises(MinecraftBranchExecutionError) as caught:
        runner.run(role=BranchRole.CONTROL, candidate=None)
    assert caught.value.phase == "execute"
    assert caught.value.cleanup_cause is not None

