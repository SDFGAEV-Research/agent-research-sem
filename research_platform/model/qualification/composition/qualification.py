"""Composition root for the deployment qualification seams."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from research_platform.model.qualification.api import (
    DeploymentCapabilityProbePort,
    DeploymentQualificationEvidenceRecord,
    DeploymentQualificationEvidenceStorePort,
    DeploymentQualificationPlan,
    DeploymentQualificationPort,
    DeploymentQualificationRequest,
)
from research_platform.model.qualification.providers.qualification_probe import LocalDeploymentCapabilityProbe
from research_platform.model.qualification.providers.qualification_evidence import (
    FileDeploymentQualificationEvidenceStore,
)
from research_platform.model.qualification.runtime.qualification import DeploymentQualificationResolver


class LocalDeploymentQualification(DeploymentQualificationPort):
    """Composition-selected implementation of the pure qualification port."""

    def __init__(
        self,
        probe: DeploymentCapabilityProbePort,
        resolver: DeploymentQualificationResolver,
        evidence: DeploymentQualificationEvidenceStorePort,
    ) -> None:
        self._probe = probe
        self._resolver = resolver
        self._evidence = evidence

    def qualify(self, request: DeploymentQualificationRequest) -> DeploymentQualificationPlan:
        facts = self._probe.capture(request)
        plan = self._resolver.resolve(request, facts)
        self._evidence.publish(
            DeploymentQualificationEvidenceRecord(
                captured_at_unix=facts.captured_at_unix,
                request=request,
                facts=facts,
                plan=plan,
            )
        )
        return plan


@dataclass(frozen=True, slots=True)
class DeploymentQualificationAuthorities:
    qualification: DeploymentQualificationPort
    evidence: DeploymentQualificationEvidenceStorePort


def build_local_deployment_qualification(
    evidence_root: Path,
) -> DeploymentQualificationAuthorities:
    evidence = FileDeploymentQualificationEvidenceStore(evidence_root)
    return DeploymentQualificationAuthorities(
        qualification=LocalDeploymentQualification(
            LocalDeploymentCapabilityProbe(),
            DeploymentQualificationResolver(),
            evidence,
        ),
        evidence=evidence,
    )


__all__ = [
    "DeploymentQualificationAuthorities",
    "LocalDeploymentQualification",
    "build_local_deployment_qualification",
]
