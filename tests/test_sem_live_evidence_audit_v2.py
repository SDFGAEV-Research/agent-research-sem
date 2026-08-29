from __future__ import annotations

from dataclasses import asdict
import hashlib
import inspect
import json
from pathlib import Path

from scripts.sem_paper_architecture_audit import (
    _is_qualified_model_closure,
    _is_t2b_gate_pass,
    _t2b_changed_paths_are_non_runtime,
    _t2b_evidence_paths,
    _t2b_source_is_current,
    build_findings,
)
from research_platform.model.serving.api import (
    DeploymentPlacement,
    QualificationCertificate,
    QualifiedDeploymentManifest,
    ResourceEnvelope,
    RoleModelAssignment,
    RoleModelManifest,
    RuntimeQualificationReceipt,
)
from research_platform.model.serving.endpoint.api import ModelEndpointRoute
from research_platform.model.serving.providers.runtime_qualification_storage import (
    DirectoryRuntimeQualificationEvidenceStore,
)
from research_platform.model.stack.api import ModelArtifactClosure, ModelStackSpec, RuntimeBuildIdentity
from research_platform.platform.kernel import ImmutableModelIdentity


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _write_valid_closure(root: Path) -> Path:
    identity = ImmutableModelIdentity(
        "sem-planner", "sem-qwen38-27b", "revision-v1", "vllm", "0.27.1", "bf16", None, 262144
    )
    stack = ModelStackSpec(
        identity,
        ModelArtifactClosure(_digest("a"), _digest("b"), _digest("c")),
        RuntimeBuildIdentity(
            _digest("d"), _digest("e"), _digest("f"), "cuda-12", "nccl", "torch", _digest("g")
        ),
        1, 1, 1, 1, None, None, None, None, "fcfs",
    )
    host_digest = _digest("h")
    certificate = QualificationCertificate(
        stack.digest(),
        _digest("i"),
        ("planner",),
        ResourceEnvelope(1, 1, 1, 1.0, 1.0, 1.0),
        host_digest,
    )
    deployment = QualifiedDeploymentManifest(
        "sem-qwen38-planner",
        stack,
        certificate,
        DeploymentPlacement(("GPU-test",)),
        host_digest,
    )
    route = ModelEndpointRoute(
        deployment.deployment_id,
        deployment.digest(),
        "http://127.0.0.1:30080",
    )
    roles = RoleModelManifest((RoleModelAssignment("planner", deployment.deployment_id),))
    runtime_manifest_digest = _digest("j")
    store = DirectoryRuntimeQualificationEvidenceStore(root / "qualification")
    store.publish(
        runtime_manifest_digest,
        RuntimeQualificationReceipt(
            deployment_id=deployment.deployment_id,
            stack_digest=stack.digest(),
            qualification_certificate_digest=certificate.digest(),
            heartbeat_qualification_digest=certificate.digest(),
            qualified_roles=("planner",),
            evidence_refs=("live:planner-canary",),
            created_at=1.0,
        ),
    )
    closure_path = root / "qualified-model-closure.json"
    closure_path.write_text(
        json.dumps(
            {
                "schema_version": "qualified-model-deployment-closure.v1",
                "runtime_manifest_digest": runtime_manifest_digest,
                "runtime_qualification_root": "qualification",
                "role_manifest": asdict(roles),
                "deployments": [asdict(deployment)],
                "routes": [asdict(route)],
            }
        ),
        encoding="utf-8",
    )
    return closure_path


def test_committed_t2b_artifact_satisfies_semantic_gate() -> None:
    gate = Path("artifacts/sem_live_evidence/35dddf3e7e8d/t2b/T2B_GATE_RESULT.json")
    assert _is_t2b_gate_pass(gate)


def test_t2b_status_only_file_cannot_close_live_gate(tmp_path: Path) -> None:
    fake = tmp_path / "T2B_GATE_RESULT.json"
    fake.write_text(json.dumps({"status": "T2B_GATE_PASS"}), encoding="utf-8")
    assert not _is_t2b_gate_pass(fake)


def test_t2b_tampered_seed_evidence_is_rejected(tmp_path: Path) -> None:
    source = Path("artifacts/sem_live_evidence/35dddf3e7e8d/t2b/T2B_GATE_RESULT.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["runs"][1]["result"]["grounded_record_count"] = 0
    tampered = tmp_path / "T2B_GATE_RESULT.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    assert not _is_t2b_gate_pass(tampered)


def test_qualified_closure_must_reconstruct_exact_planner_binding(tmp_path: Path) -> None:
    assert _is_qualified_model_closure(_write_valid_closure(tmp_path))


def test_closure_filename_and_schema_without_runtime_receipt_are_insufficient(tmp_path: Path) -> None:
    fake = tmp_path / "qualified-model-closure.json"
    fake.write_text(
        json.dumps(
            {
                "schema_version": "qualified-model-deployment-closure.v1",
                "runtime_qualification_root": "missing-qualification",
            }
        ),
        encoding="utf-8",
    )
    assert not _is_qualified_model_closure(fake)
    assert not (tmp_path / "missing-qualification").exists()


def test_current_live_finding_reports_only_remaining_model_closure_gap() -> None:
    finding = next(item for item in build_findings() if item.finding_id == "LIVE_EXECUTION_EVIDENCE")
    assert finding.status == "open"
    assert finding.evidence == "qualified planner deployment closure is missing"


def test_current_t2b_provenance_is_compatible_with_evidence_only_descendants() -> None:
    gate = Path("artifacts/sem_live_evidence/d797550ea1b5/t2b/T2B_GATE_RESULT.json")
    assert _t2b_source_is_current(gate)


def test_superseded_t2b_provenance_is_rejected_after_runtime_sensitive_change() -> None:
    stale_gate = Path("artifacts/sem_live_evidence/35dddf3e7e8d/t2b/T2B_GATE_RESULT.json")
    assert not _t2b_source_is_current(stale_gate)


def test_t2b_inheritance_allows_only_non_runtime_paths() -> None:
    assert _t2b_changed_paths_are_non_runtime(
        (
            "artifacts/sem_live_evidence/example/T2B_GATE_RESULT.json",
            "projects/sem_paper/governance/cross_system_change_requests/CSR.md",
            "scripts/sem_paper_architecture_audit.py",
            "tests/test_sem_live_evidence_audit_v2.py",
        )
    )


def test_t2b_inheritance_rejects_runtime_sensitive_drift() -> None:
    for path in (
        "projects/sem_paper/composition/minecraft_workload.py",
        "scripts/sem_paper_minecraft_application.py",
        "research_platform/environment/minecraft/runtime/session.py",
    ):
        assert not _t2b_changed_paths_are_non_runtime((path,))


def test_t2b_discovery_is_scoped_to_live_evidence_authority() -> None:
    paths = _t2b_evidence_paths()
    normalized = {path.replace("\\", "/") for path in paths}
    assert "artifacts/sem_live_evidence/d797550ea1b5/t2b/T2B_GATE_RESULT.json" in normalized
    assert all(path.replace("\\", "/").startswith("artifacts/sem_live_evidence/") for path in paths)


def test_closure_schema_authority_is_delegated_to_platform_loader() -> None:
    source = inspect.getsource(_is_qualified_model_closure)
    assert "qualified-model-deployment-closure.v1" not in source
    assert "load_qualified_model_deployment_closure" in source
