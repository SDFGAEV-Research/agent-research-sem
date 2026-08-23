from __future__ import annotations

from dataclasses import replace
import json

import pytest

from research_platform.environment.minecraft.api import MinecraftWorldCut
from research_platform.experimentation.checkpoint.api import (
    WorkloadExecutionCut,
    build_workload_checkpoint_manifest,
)
from research_platform.experimentation.run.runtime import DirectoryRunArtifactStore
from scripts.sem_paper_minecraft_application import (
    ExperimentConfigurationError,
    MinecraftResumeIdentity,
    MinecraftResumeIndex,
)


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
    digest = "a" * 64
    return MinecraftWorldCut(
        cut_id="cut-1",
        snapshot_ref="/runs/run-1/world-cuts/cut-1",
        manifest_ref="/runs/run-1/world-cuts/cut-1.json",
        level_name="world",
        server_contract_digest=digest,
        process_identity_digest="b" * 64,
        manifest_digest="c" * 64,
        save_evidence_ref="/runs/run-1/evidence/save.json",
    )


def _manifest(*, source_cut_id: str = "cut-1"):
    return build_workload_checkpoint_manifest(
        run_id="run-1",
        study_id="sem-paper-minecraft",
        workload_id="sem-paper:paired:run-1",
        branch_id="run-1:control:rep-0",
        source_cut_id=source_cut_id,
        environment_generation="environment-1",
        method_generation="method-1",
        task_manifest_digest="3" * 64,
        execution_cut=WorkloadExecutionCut(("task-1",)),
        component_refs=(),
    )


def test_resume_index_round_trips_verified_source_cut_and_checkpoint(tmp_path) -> None:
    artifacts = DirectoryRunArtifactStore(tmp_path)
    identity = _identity()
    index = MinecraftResumeIndex.open(
        artifacts=artifacts,
        identity=identity,
        path=None,
    )
    index.persist()
    index.source_cut_published(repetition=0, cut=_cut())
    manifest = _manifest()
    index.published(manifest)

    path = tmp_path / "resume_index.json"
    loaded = MinecraftResumeIndex.open(
        artifacts=artifacts,
        identity=identity,
        path=path,
    )

    assert loaded.source_cuts == {0: _cut()}
    assert loaded.branch_checkpoints == {
        "run-1:control:rep-0": manifest.checkpoint_id,
    }


def test_resume_index_rejects_scientific_or_source_cut_drift(tmp_path) -> None:
    artifacts = DirectoryRunArtifactStore(tmp_path)
    identity = _identity()
    index = MinecraftResumeIndex.open(
        artifacts=artifacts,
        identity=identity,
        path=None,
    )
    index.source_cut_published(repetition=0, cut=_cut())

    with pytest.raises(ValueError, match="persisted source cut"):
        index.published(_manifest(source_cut_id="another-cut"))

    with pytest.raises(ExperimentConfigurationError, match="scientific identity mismatch"):
        MinecraftResumeIndex.open(
            artifacts=artifacts,
            identity=replace(identity, candidate_digest="5" * 64),
            path=tmp_path / "resume_index.json",
        )


def test_resume_index_rejects_checkpoint_without_source_cut(tmp_path) -> None:
    artifacts = DirectoryRunArtifactStore(tmp_path)
    identity = _identity()
    document = {
        "schema_version": "sem-paper.minecraft-resume-index.v1",
        "identity": {
            "run_id": identity.run_id,
            "study_id": identity.study_id,
            "run_spec_digest": identity.run_spec_digest,
            "protocol_digest": identity.protocol_digest,
            "task_manifest_digest": identity.task_manifest_digest,
            "candidate_digest": identity.candidate_digest,
            "repetitions": identity.repetitions,
        },
        "source_cuts": {},
        "branch_checkpoints": {"run-1:control:rep-0": "checkpoint-1"},
    }
    path = tmp_path / "resume_index.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ExperimentConfigurationError, match="no persisted source cut"):
        MinecraftResumeIndex.open(artifacts=artifacts, identity=identity, path=path)
