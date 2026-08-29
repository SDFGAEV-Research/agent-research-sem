from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
import time

from research_platform.model.serving.api import (
    QualifiedDeploymentManifest,
    RoleModelManifest,
    RuntimeQualificationEvidenceStorePort,
    ServiceHeartbeat,
)

from research_platform.platform.kernel import canonical_digest

from ..api import ModelEndpointRoute, QualifiedModelEndpointBinding, QualifiedModelEndpointBindingPort


@dataclass(frozen=True, slots=True)
class QualifiedModelDeploymentClosure:
    """Already-persisted deployment facts needed by one endpoint consumer.

    This is a read projection over the model/serving authorities.  It does not
    create a deployment registry and it does not infer an endpoint from a
    readiness URL or operator environment variables.
    """

    role_manifest: RoleModelManifest
    deployments: tuple[QualifiedDeploymentManifest, ...]
    routes: tuple[ModelEndpointRoute, ...]
    runtime_manifest_digest: str
    runtime_qualifications: RuntimeQualificationEvidenceStorePort


class PersistedQualifiedModelEndpointBinding(QualifiedModelEndpointBindingPort):
    """Load one endpoint binding only after all qualification identities agree."""

    def __init__(
        self,
        closure: QualifiedModelDeploymentClosure,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not closure.runtime_manifest_digest.strip():
            raise ValueError("qualified deployment closure requires runtime manifest identity")
        deployment_ids = [item.deployment_id for item in closure.deployments]
        if len(deployment_ids) != len(set(deployment_ids)):
            raise ValueError("qualified deployment closure contains duplicate deployments")
        route_ids = [item.deployment_id for item in closure.routes]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("qualified deployment closure contains duplicate routes")
        self._roles = closure.role_manifest
        self._deployments = {item.deployment_id: item for item in closure.deployments}
        self._routes = {item.deployment_id: item for item in closure.routes}
        self._runtime_manifest_digest = closure.runtime_manifest_digest
        self._runtime_qualifications = closure.runtime_qualifications
        self._clock = clock

    def binding_for(self, *, role: str, prompt_generation: str) -> QualifiedModelEndpointBinding:
        if not role.strip() or not prompt_generation.strip():
            raise ValueError("qualified model binding role and prompt generation are required")
        deployment_id = self._roles.deployment_for(role)
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            raise ValueError(f"qualified role assignment has no deployment: {deployment_id}")
        route = self._routes.get(deployment_id)
        if route is None:
            raise ValueError(f"qualified deployment has no endpoint route: {deployment_id}")
        deployment_generation = deployment.digest()
        if route.deployment_generation != deployment_generation:
            raise ValueError(f"qualified endpoint route generation drift: {deployment_id}")

        receipt = self._runtime_qualifications.load(
            self._runtime_manifest_digest,
            deployment_id,
        )
        certificate_digest = deployment.certificate.digest()
        stack_digest = deployment.stack.digest()
        if receipt.deployment_id != deployment_id:
            raise ValueError("runtime qualification receipt deployment drift")
        if receipt.stack_digest != stack_digest:
            raise ValueError("runtime qualification receipt stack drift")
        if receipt.qualification_certificate_digest != certificate_digest:
            raise ValueError("runtime qualification receipt certificate drift")
        heartbeat = ServiceHeartbeat(
            receipt.deployment_id, receipt.stack_digest, receipt.process_pid,
            receipt.process_start_marker, receipt.argv_digest, True,
            receipt.heartbeat_qualification_digest, receipt.heartbeat_timestamp,
        )
        if f"heartbeat:sha256:{canonical_digest(heartbeat)}" not in receipt.evidence_refs:
            raise ValueError("runtime qualification receipt heartbeat evidence drift")
        if role not in receipt.qualified_roles:
            raise ValueError(f"runtime qualification receipt does not qualify role: {role}")
        now = float(self._clock())
        if not math.isfinite(now):
            raise ValueError("runtime qualification binding clock must be finite")
        if receipt.created_at > now:
            raise ValueError("runtime qualification receipt is from the future")
        if receipt.valid_until < now:
            raise ValueError("runtime qualification receipt is stale")

        return QualifiedModelEndpointBinding(
            role=role,
            deployment_id=deployment_id,
            deployment_generation=deployment_generation,
            base_url=route.base_url,
            model=deployment.stack.identity,
            model_stack_digest=stack_digest,
            qualification_certificate_digest=certificate_digest,
            runtime_qualification_digest=receipt.digest(),
            host_identity_digest=deployment.host_identity_digest,
            prompt_generation=prompt_generation,
            max_admitted_concurrency=deployment.certificate.resource_envelope.max_qualified_concurrency,
            completion_path=route.completion_path,
            timeout_s=route.timeout_s,
        )


__all__ = [
    "PersistedQualifiedModelEndpointBinding",
    "QualifiedModelDeploymentClosure",
]
