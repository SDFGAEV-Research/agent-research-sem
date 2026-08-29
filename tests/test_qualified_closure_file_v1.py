from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

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
from research_platform.model.serving.endpoint.providers import (
    PersistedQualifiedModelEndpointBinding,
    load_qualified_model_deployment_closure,
)
from research_platform.model.serving.providers.runtime_qualification_storage import (
    DirectoryRuntimeQualificationEvidenceStore,
)
from research_platform.model.stack.api import ModelArtifactClosure, ModelStackSpec, RuntimeBuildIdentity
from research_platform.platform.kernel import ImmutableModelIdentity


def _digest(seed: str) -> str:
    return (seed * 64)[:64]


class QualifiedClosureFileTests(unittest.TestCase):
    def test_file_reader_reconstructs_and_binds_one_qualified_role(self) -> None:
        identity = ImmutableModelIdentity(
            "planner-model",
            "model-v1",
            "revision-v1",
            "vllm",
            "0.1",
            "bf16",
            None,
            8192,
        )
        stack = ModelStackSpec(
            identity,
            ModelArtifactClosure(_digest("a"), _digest("b"), _digest("c")),
            RuntimeBuildIdentity(
                _digest("d"), _digest("e"), _digest("f"), "cuda", "nccl", "torch", _digest("a")
            ),
            1,
            1,
            1,
            1,
            None,
            None,
            None,
            None,
            "fcfs",
        )
        certificate = QualificationCertificate(
            stack.digest(),
            _digest("f"),
            ("planner",),
            ResourceEnvelope(1, 1, 1, 1.0, 1.0, 1.0),
            _digest("b"),
        )
        deployment = QualifiedDeploymentManifest(
            "deployment-1",
            stack,
            certificate,
            DeploymentPlacement(("GPU-1",)),
            _digest("b"),
        )
        route = ModelEndpointRoute(
            deployment.deployment_id,
            deployment.digest(),
            "http://127.0.0.1:30000",
            timeout_s=17.0,
        )
        roles = RoleModelManifest((RoleModelAssignment("planner", deployment.deployment_id),))
        runtime_manifest_digest = _digest("c")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            runtime_store = DirectoryRuntimeQualificationEvidenceStore(root / "qualification")
            receipt = RuntimeQualificationReceipt(
                deployment_id=deployment.deployment_id,
                stack_digest=stack.digest(),
                qualification_certificate_digest=certificate.digest(),
                heartbeat_qualification_digest=certificate.digest(),
                qualified_roles=("planner",),
                evidence_refs=("evidence:planner",),
                created_at=1.0,
            )
            runtime_store.publish(runtime_manifest_digest, receipt)
            closure_path = root / "closure.json"
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

            closure = load_qualified_model_deployment_closure(
                closure_path,
                runtime_qualification_store_factory=DirectoryRuntimeQualificationEvidenceStore,
            )
            binding = PersistedQualifiedModelEndpointBinding(closure).binding_for(
                role="planner",
                prompt_generation="prompt-generation-v1",
            )

        self.assertEqual(binding.deployment_id, "deployment-1")
        self.assertEqual(binding.model, identity)
        self.assertEqual(binding.timeout_s, 17.0)
        self.assertEqual(binding.max_admitted_concurrency, 1)


if __name__ == "__main__":
    unittest.main()
