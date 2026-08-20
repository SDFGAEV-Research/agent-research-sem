from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from research_platform.reliability.primitives.runtime_faults import FrozenRuntimeIdentityViolation, RuntimeOperationalHealthUnavailable
from research_platform.runtime.service.api import ServiceContractDrift, ServiceLaunchContract, ExactServiceRuntimePort


from .contracts import FrozenRuntimeManifest


@dataclass(frozen=True, slots=True)
class RunLaunchIdentity:
    """Runtime identity that must remain unchanged when launching/resuming the Run process."""

    release_digest: str
    experiment_spec_digest: str
    participant_binding_manifest_digest: str
    seed_identity: str

    @classmethod
    def from_manifest(cls, manifest: FrozenRuntimeManifest) -> "RunLaunchIdentity":
        return cls(
            manifest.release_digest,
            manifest.experiment_spec_digest,
            manifest.participant_binding_manifest_digest,
            manifest.seed_identity,
        )

    def digest(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class RunProcessBinding:
    identity: RunLaunchIdentity
    launch_contract: ServiceLaunchContract
    runtime: ExactServiceRuntimePort

    def __post_init__(self) -> None:
        if self.launch_contract.generation != self.identity.digest():
            raise ValueError("run service generation must equal frozen Run launch identity digest")


class RunProcessBindingError(FrozenRuntimeIdentityViolation):
    pass


class ExactRunProcessPort:
    """RunProcessPort backed by the generic service supervisor, independent of participant kinds."""

    def __init__(self, binding: RunProcessBinding) -> None:
        self.binding = binding

    def _verify(self, manifest: FrozenRuntimeManifest) -> None:
        expected = RunLaunchIdentity.from_manifest(manifest)
        if expected != self.binding.identity:
            raise RunProcessBindingError("frozen runtime manifest differs from Run launch identity")
        if self.binding.launch_contract.generation != expected.digest():
            raise RunProcessBindingError("Run launch contract generation drift")

    def reconcile(self, manifest: FrozenRuntimeManifest) -> tuple[str, ...]:
        self._verify(manifest)
        contract = self.binding.launch_contract
        try:
            observation = self.binding.runtime.reconcile_exact(contract)
        except ServiceContractDrift as exc:
            raise RunProcessBindingError("run service runtime contract drift") from exc
        if not observation.state_present:
            return ("run-reconcile:no-state",)
        status = "missing" if observation.process is None else f"exact:{observation.process.start_identity}"
        return tuple(observation.evidence_refs) + (f"run-reconcile:{status}",)

    def start_exact(self, manifest: FrozenRuntimeManifest) -> tuple[str, ...]:
        self._verify(manifest)
        try:
            report = self.binding.runtime.start_exact(self.binding.launch_contract)
        except ServiceContractDrift as exc:
            raise RunProcessBindingError("run service runtime contract drift") from exc
        return tuple(report.evidence_refs) + (f"run-running:{report.contract_digest}",)

    def final_status(self, manifest: FrozenRuntimeManifest) -> tuple[str, ...]:
        self._verify(manifest)
        try:
            ready = self.binding.runtime.verify_ready_exact(self.binding.launch_contract)
        except ServiceContractDrift as exc:
            raise RunProcessBindingError("run service runtime contract drift") from exc
        except RuntimeError as exc:
            raise RuntimeOperationalHealthUnavailable("Run process is not running at FINAL_STATUS") from exc
        return tuple(ready.evidence_refs) + (
            ready.ready_evidence_ref,
            f"run-final:{ready.process.start_identity}:{manifest.experiment_spec_digest}",
        )


__all__ = ["ExactRunProcessPort", "RunLaunchIdentity", "RunProcessBinding", "RunProcessBindingError"]
