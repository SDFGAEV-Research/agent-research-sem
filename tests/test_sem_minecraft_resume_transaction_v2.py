from __future__ import annotations

import pytest

from projects.sem_paper.composition.minecraft_resume import (
    MinecraftResumeIdentity,
    MinecraftResumeIndex,
)
from research_platform.environment.minecraft.api import MinecraftWorldCut
from research_platform.experimentation.checkpoint.api import (
    WorkloadExecutionCut,
    build_workload_checkpoint_manifest,
)


class _Artifacts:
    def __init__(self) -> None:
        self.fail = False
        self.documents: list[dict] = []

    def publish_json(self, name, payload, *, kind):
        del name, kind
        if self.fail:
            raise OSError("artifact publication unavailable")
        self.documents.append(dict(payload))


def _identity() -> MinecraftResumeIdentity:
    return MinecraftResumeIdentity(
        run_id="run-1",
        study_id="sem-paper-minecraft",
        run_spec_digest="1" * 64,
        protocol_digest="2" * 64,
        task_manifest_digest="3" * 64,
        candidate_digest="4" * 64,
        repetitions=1,
    )


def _cut() -> MinecraftWorldCut:
    return MinecraftWorldCut(
        cut_id="cut-1",
        snapshot_ref="/runs/run-1/world-cuts/cut-1",
        manifest_ref="/runs/run-1/world-cuts/cut-1.json",
        level_name="world",
        server_contract_digest="a" * 64,
        process_identity_digest="b" * 64,
        manifest_digest="c" * 64,
        save_evidence_ref="/runs/run-1/evidence/save.json",
    )


def _manifest():
    return build_workload_checkpoint_manifest(
        run_id="run-1",
        study_id="sem-paper-minecraft",
        workload_id="sem-paper:paired:run-1",
        branch_id="run-1:control:rep-0",
        source_cut_id="cut-1",
        environment_generation="environment-1",
        method_generation="method-1",
        task_manifest_digest="3" * 64,
        execution_cut=WorkloadExecutionCut(("task-1",)),
        component_refs=(),
    )


def test_failed_source_cut_publish_does_not_commit_memory_state() -> None:
    artifacts = _Artifacts()
    index = MinecraftResumeIndex(
        artifacts=artifacts,
        identity=_identity(),
    )
    artifacts.fail = True
    with pytest.raises(OSError, match="publication unavailable"):
        index.source_cut_published(repetition=0, cut=_cut())
    assert index.source_cuts == {}
    assert index.branch_checkpoints == {}

    artifacts.fail = False
    index.source_cut_published(repetition=0, cut=_cut())
    assert index.source_cuts == {0: _cut()}


def test_failed_checkpoint_publish_does_not_create_ghost_checkpoint() -> None:
    artifacts = _Artifacts()
    index = MinecraftResumeIndex(
        artifacts=artifacts,
        identity=_identity(),
    )
    index.source_cut_published(repetition=0, cut=_cut())

    artifacts.fail = True
    manifest = _manifest()
    with pytest.raises(OSError, match="publication unavailable"):
        index.published(manifest)
    assert index.branch_checkpoints == {}

    artifacts.fail = False
    index.published(manifest)
    assert index.branch_checkpoints == {
        "run-1:control:rep-0": manifest.checkpoint_id,
    }


def test_resume_identity_rejects_coercible_counts_and_noncanonical_digests() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        MinecraftResumeIdentity(
            run_id="run-1",
            study_id="sem-paper-minecraft",
            run_spec_digest="1" * 64,
            protocol_digest="2" * 64,
            task_manifest_digest="3" * 64,
            candidate_digest="4" * 64,
            repetitions=True,
        )
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        MinecraftResumeIdentity(
            run_id="run-1",
            study_id="sem-paper-minecraft",
            run_spec_digest="A" * 64,
            protocol_digest="2" * 64,
            task_manifest_digest="3" * 64,
            candidate_digest="4" * 64,
            repetitions=1,
        )
