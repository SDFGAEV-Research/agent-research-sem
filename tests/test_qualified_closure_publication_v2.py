from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import threading
import time

import pytest

from research_platform.model.serving.api import (
    DeploymentPlacement,
    QualificationCertificate,
    QualifiedDeploymentManifest,
    ResourceEnvelope,
    RoleModelAssignment,
    RoleModelManifest,
    RuntimeQualificationReceipt,
    ServiceHeartbeat,
    build_runtime_qualification_receipt,
)
from research_platform.model.serving.composition import publish_qualified_model_deployment_closure
from research_platform.model.serving.endpoint.api import (
    ModelEndpointRoute,
    QualifiedModelClosurePublication,
)
from research_platform.model.serving.endpoint.providers import (
    PersistedQualifiedModelEndpointBinding,
    QualifiedModelClosurePublicationError,
    QualifiedModelClosureReadError,
    load_qualified_model_deployment_closure,
    publish_qualified_model_deployment_closure as _publish_with_store,
)
from research_platform.model.serving.providers.runtime_qualification_storage import DirectoryRuntimeQualificationEvidenceStore
from research_platform.model.stack.api import ModelArtifactClosure, ModelStackSpec, RuntimeBuildIdentity
from research_platform.platform.kernel import ImmutableModelIdentity, canonical_digest


def _digest(seed: str) -> str:
    return (seed * 64)[:64]


def _publication() -> QualifiedModelClosurePublication:
    identity = ImmutableModelIdentity(
        "planner-model", "repo/model", "revision", "vllm", "0.1",
        "bfloat16", None, 8192,
    )
    stack = ModelStackSpec(
        identity,
        ModelArtifactClosure(
            _digest("a"), _digest("b"), _digest("c"), _digest("d"), _digest("e")
        ),
        RuntimeBuildIdentity(
            _digest("f"), _digest("1"), _digest("2"),
            "cuda-12.8", "nccl-2.27", "torch-2.8", _digest("3"),
        ),
        1, 1, 1, 1,
        None, None, None, None, "fcfs", (),
    )
    certificate = QualificationCertificate(
        stack.digest(), _digest("4"), ("planner",),
        ResourceEnvelope(70 << 30, 100 << 30, 2, 1.0, 0.1, 100.0),
        _digest("5"),
    )
    deployment = QualifiedDeploymentManifest(
        "deployment-1", stack, certificate, DeploymentPlacement(("GPU-1",)), _digest("5")
    )
    route = ModelEndpointRoute(
        deployment.deployment_id,
        deployment.digest(),
        "http://127.0.0.1:30000",
        timeout_s=17.0,
    )
    roles = RoleModelManifest((RoleModelAssignment("planner", deployment.deployment_id),))
    now = time.time()
    heartbeat = ServiceHeartbeat(
        deployment.deployment_id, stack.digest(), 123, "start-123", _digest("7"),
        True, certificate.digest(), now - 0.1,
    )
    heartbeat_ref = (
        f"heartbeat:{heartbeat.deployment_id}:{heartbeat.pid}:"
        f"{heartbeat.process_start_marker}:{heartbeat.timestamp}"
    )
    receipt = build_runtime_qualification_receipt(
        deployment, heartbeat, required_roles=("planner",),
        evidence_refs=(heartbeat_ref,), max_heartbeat_age_seconds=60.0, now=now,
    )
    return QualifiedModelClosurePublication(
        role_manifest=roles,
        deployments=(deployment,),
        routes=(route,),
        runtime_manifest_digest=_digest("6"),
        runtime_qualification_receipts=(receipt,),
    )


def test_publisher_round_trip_produces_bindable_closure(tmp_path: Path) -> None:
    publication = _publication()
    path = tmp_path / "qualified.json"
    receipt = publish_qualified_model_deployment_closure(path, publication)

    closure = load_qualified_model_deployment_closure(
        path,
        runtime_qualification_store_factory=DirectoryRuntimeQualificationEvidenceStore,
    )
    binding = PersistedQualifiedModelEndpointBinding(closure).binding_for(
        role="planner", prompt_generation="prompt-v1"
    )

    assert receipt.closure_path == str(path.resolve())
    assert len(receipt.closure_digest) == 64
    assert len(receipt.runtime_evidence_paths) == 1
    assert binding.deployment_id == "deployment-1"
    assert binding.max_admitted_concurrency == 2
    assert binding.runtime_qualification_digest == publication.runtime_qualification_receipts[0].digest()


def test_identical_replay_is_idempotent_and_conflict_is_rejected(tmp_path: Path) -> None:
    publication = _publication()
    path = tmp_path / "qualified.json"
    first = publish_qualified_model_deployment_closure(path, publication)
    before = path.read_bytes()
    second = publish_qualified_model_deployment_closure(path, publication)
    assert second.closure_digest == first.closure_digest
    assert path.read_bytes() == before

    changed_route = replace(publication.routes[0], base_url="http://127.0.0.1:30001")
    conflicting = replace(publication, routes=(changed_route,))
    with pytest.raises(QualifiedModelClosurePublicationError, match="different content"):
        publish_qualified_model_deployment_closure(path, conflicting)
    assert path.read_bytes() == before


def test_valid_recomputed_digest_does_not_hide_type_corruption(tmp_path: Path) -> None:
    publication = _publication()
    path = tmp_path / "qualified.json"
    publish_qualified_model_deployment_closure(path, publication)
    document = json.loads(path.read_text(encoding="utf-8"))
    envelope = document["deployments"][0]["certificate"]["resource_envelope"]
    envelope["max_qualified_concurrency"] = "2"
    unsigned = {key: value for key, value in document.items() if key != "closure_digest"}
    document["closure_digest"] = canonical_digest(unsigned)
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(QualifiedModelClosureReadError):
        load_qualified_model_deployment_closure(
            path,
            runtime_qualification_store_factory=DirectoryRuntimeQualificationEvidenceStore,
        )


class _FailingReadbackStore:
    def publish(self, runtime_manifest_digest: str, receipt: RuntimeQualificationReceipt) -> str:
        del runtime_manifest_digest
        return f"memory:{receipt.deployment_id}"

    def load(self, runtime_manifest_digest: str, deployment_id: str) -> RuntimeQualificationReceipt:
        del runtime_manifest_digest, deployment_id
        raise OSError("injected readback failure")


def test_partial_runtime_publication_never_exposes_closure(tmp_path: Path) -> None:
    path = tmp_path / "qualified.json"
    with pytest.raises(QualifiedModelClosurePublicationError, match="runtime qualification publication"):
        _publish_with_store(
            path,
            _publication(),
            runtime_qualification_store_factory=lambda root: _FailingReadbackStore(),
        )
    assert not path.exists()


def test_runtime_receipt_must_cover_frozen_role_before_any_write(tmp_path: Path) -> None:
    publication = _publication()
    bad_receipt = replace(publication.runtime_qualification_receipts[0], qualified_roles=("critic",))
    invalid = replace(publication, runtime_qualification_receipts=(bad_receipt,))
    path = tmp_path / "qualified.json"
    with pytest.raises(QualifiedModelClosurePublicationError, match="frozen roles"):
        publish_qualified_model_deployment_closure(path, invalid)
    assert not path.exists()


def test_conflicting_closure_is_rejected_before_new_runtime_evidence(tmp_path: Path) -> None:
    publication = _publication()
    path = tmp_path / "qualified.json"
    publish_qualified_model_deployment_closure(path, publication)

    conflicting = replace(publication, runtime_manifest_digest=_digest("7"))
    with pytest.raises(QualifiedModelClosurePublicationError, match="different content"):
        publish_qualified_model_deployment_closure(path, conflicting)

    unexpected = tmp_path / publication.runtime_qualification_root / conflicting.runtime_manifest_digest
    assert not unexpected.exists()


def test_concurrent_identical_publishers_share_one_publication_domain(tmp_path: Path) -> None:
    publication = _publication()
    path = tmp_path / "qualified.json"
    barrier = threading.Barrier(6)
    receipts = []
    failures: list[BaseException] = []

    def publish() -> None:
        try:
            barrier.wait()
            receipts.append(publish_qualified_model_deployment_closure(path, publication))
        except BaseException as exc:
            failures.append(exc)

    threads = [threading.Thread(target=publish) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(3.0)

    assert all(not thread.is_alive() for thread in threads)
    assert failures == []
    assert len(receipts) == 6
    assert len({item.closure_digest for item in receipts}) == 1
    assert path.is_file()
