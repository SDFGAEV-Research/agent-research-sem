from __future__ import annotations

import json

import pytest

from research_platform.experimentation.checkpoint.api import (
    RunCheckpointIntegrityError,
    WorkloadCheckpointComponentRef,
    WorkloadExecutionCut,
    build_workload_checkpoint_manifest,
)
from research_platform.experimentation.checkpoint.providers.workload_codec import (
    WorkloadCheckpointManifestCodec,
)


def _encoded() -> dict[str, object]:
    ref = WorkloadCheckpointComponentRef(
        "component-1", "codec-1", "1", "a" * 64, 4
    )
    manifest = build_workload_checkpoint_manifest(
        run_id="run-1", study_id="study-1", workload_id="workload-1",
        branch_id="branch-1", source_cut_id="cut-1",
        environment_generation="env-1", method_generation="method-1",
        task_manifest_digest="tasks-1",
        execution_cut=WorkloadExecutionCut(("task-1",)), component_refs=(ref,),
    )
    return json.loads(WorkloadCheckpointManifestCodec.encode(manifest))


def _decode(document: dict[str, object]) -> None:
    WorkloadCheckpointManifestCodec.decode(
        json.dumps(document, separators=(",", ":")).encode("utf-8")
    )


def test_workload_checkpoint_manifest_codec_round_trip() -> None:
    _decode(_encoded())


@pytest.mark.parametrize("mutation", ["envelope_extra", "manifest_extra", "digest_type"])
def test_workload_checkpoint_manifest_codec_rejects_schema_drift(mutation: str) -> None:
    document = _encoded()
    if mutation == "envelope_extra":
        document["unexpected"] = True
    elif mutation == "manifest_extra":
        document["manifest"]["unexpected"] = True
    else:
        document["manifest_digest"] = 7
    with pytest.raises(RunCheckpointIntegrityError):
        _decode(document)


@pytest.mark.parametrize("field,value", [("payload_size", True), ("codec_id", 7)])
def test_workload_checkpoint_manifest_codec_rejects_component_type_drift(field, value) -> None:
    document = _encoded()
    document["manifest"]["component_refs"][0][field] = value
    with pytest.raises(RunCheckpointIntegrityError):
        _decode(document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("completed_task_ids", "task-1"),
        ("current_task_id", 1),
        ("decision_cycle_id", False),
        ("status", 1),
    ],
)
def test_workload_checkpoint_manifest_codec_rejects_execution_cut_type_drift(
    field, value
) -> None:
    document = _encoded()
    document["manifest"]["execution_cut"][field] = value
    with pytest.raises(RunCheckpointIntegrityError):
        _decode(document)
