from __future__ import annotations

import json
import hashlib

import pytest

from research_platform.experimentation.checkpoint.api import (
    RunCheckpointBundle,
    RunCheckpointIntegrityError,
    RunCheckpointManifest,
    RunParticipantPayload,
    RunParticipantSnapshotRef,
)
from research_platform.experimentation.checkpoint.providers import DirectoryRunCheckpointStore
from research_platform.experimentation.checkpoint.providers.codec import RunCheckpointManifestCodec
from research_platform.participant.core.api.checkpoint import ParticipantCheckpoint, ParticipantCheckpointRef


def _encoded() -> dict[str, object]:
    participant = ParticipantCheckpointRef(
        role="agent", runtime_binding_digest="binding-1",
        component_digest="component-1", session_id="session-1",
        payload_sha256="a" * 64,
    )
    manifest = RunCheckpointManifest(
        checkpoint_id="checkpoint-1", schema_version="4",
        experiment_spec_digest="spec-1", run_id="run-1", session_id="session-1",
        decision_cycle_id="cycle-1", cycle_identity_digest="cycle-digest-1",
        participant_snapshots=(RunParticipantSnapshotRef(participant, "generation-1"),),
    )
    return json.loads(RunCheckpointManifestCodec.encode(manifest))


def _decode(document: dict[str, object]) -> None:
    RunCheckpointManifestCodec.decode(
        json.dumps(document, separators=(",", ":")).encode("utf-8")
    )


def test_run_checkpoint_manifest_codec_round_trip() -> None:
    _decode(_encoded())


@pytest.mark.parametrize("mutation", ["envelope_extra", "manifest_extra", "digest_type"])
def test_run_checkpoint_manifest_codec_rejects_schema_drift(mutation: str) -> None:
    document = _encoded()
    if mutation == "envelope_extra":
        document["unexpected"] = True
    elif mutation == "manifest_extra":
        document["manifest"]["unexpected"] = True
    else:
        document["manifest_digest"] = 9
    with pytest.raises(RunCheckpointIntegrityError):
        _decode(document)


@pytest.mark.parametrize("field,value", [("generation", 1), ("generation", False)])
def test_run_checkpoint_manifest_codec_rejects_snapshot_type_drift(field, value) -> None:
    document = _encoded()
    document["manifest"]["participant_snapshots"][0][field] = value
    with pytest.raises(RunCheckpointIntegrityError):
        _decode(document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("role", 1),
        ("runtime_binding_digest", False),
        ("payload_sha256", 7),
    ],
)
def test_run_checkpoint_manifest_codec_rejects_participant_ref_type_drift(
    field, value
) -> None:
    document = _encoded()
    document["manifest"]["participant_snapshots"][0]["checkpoint"][field] = value
    with pytest.raises(RunCheckpointIntegrityError):
        _decode(document)


def _bundle_fixture() -> tuple[RunCheckpointManifest, RunParticipantPayload]:
    payload = b"agent-state"
    checkpoint_ref = ParticipantCheckpointRef(
        role="agent", runtime_binding_digest="binding-1",
        component_digest="component-1", session_id="session-1",
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )
    snapshot = RunParticipantSnapshotRef(checkpoint_ref, "generation-1")
    manifest = RunCheckpointManifest(
        checkpoint_id="checkpoint-1", schema_version="4",
        experiment_spec_digest="spec-1", run_id="run-1", session_id="session-1",
        decision_cycle_id="cycle-1", cycle_identity_digest="cycle-digest-1",
        participant_snapshots=(snapshot,),
    )
    return manifest, RunParticipantPayload(snapshot, ParticipantCheckpoint(checkpoint_ref, payload))


def test_run_checkpoint_bundle_rejects_duplicate_payload_roles() -> None:
    manifest, payload = _bundle_fixture()
    with pytest.raises(ValueError, match="payload roles must be unique"):
        RunCheckpointBundle(manifest, (payload, payload))


def test_run_checkpoint_bundle_requires_exact_manifest_payload_set() -> None:
    manifest, _payload = _bundle_fixture()
    with pytest.raises(ValueError, match="payload roles must match the manifest"):
        RunCheckpointBundle(manifest, ())


def test_run_checkpoint_store_rejects_duplicate_payloads_before_blob_write(tmp_path) -> None:
    manifest, payload = _bundle_fixture()
    store = DirectoryRunCheckpointStore(tmp_path / "run-checkpoint-store")
    with pytest.raises(RunCheckpointIntegrityError):
        store.publish(manifest, (payload, payload))
    assert not any(store.blobs.rglob("*.bin"))
