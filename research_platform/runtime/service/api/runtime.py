from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import ServiceLaunchContract, ServiceProcessIdentity


@dataclass(frozen=True, slots=True)
class ServiceReconcileObservation:
    state_present: bool
    process: ServiceProcessIdentity | None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ServiceStartOutcome:
    contract_digest: str
    process: ServiceProcessIdentity
    ready_evidence_ref: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ServiceStopOutcome:
    contract_digest: str
    stopped: bool
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ServiceReadyObservation:
    contract_digest: str
    process: ServiceProcessIdentity
    ready_evidence_ref: str
    evidence_refs: tuple[str, ...] = ()


class ExactServiceRuntimePort(Protocol):
    """Cross-system semantic Service runtime ABI; no supervisor state escapes."""

    def reconcile_exact(self, contract: ServiceLaunchContract) -> ServiceReconcileObservation: ...
    def start_exact(self, contract: ServiceLaunchContract) -> ServiceStartOutcome: ...
    def verify_ready_exact(self, contract: ServiceLaunchContract) -> ServiceReadyObservation: ...
    def stop_exact(self, contract: ServiceLaunchContract) -> ServiceStopOutcome: ...


__all__ = [
    "ExactServiceRuntimePort",
    "ServiceReadyObservation",
    "ServiceReconcileObservation",
    "ServiceStartOutcome",
    "ServiceStopOutcome",
]
