from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research_platform.platform.kernel import canonical_digest



class RuntimeAction(StrEnum):
    VERIFY_RELEASE = "verify_release"
    VERIFY_PROMPT_PROMOTION = "verify_prompt_promotion"
    VERIFY_HOST_INVENTORY = "verify_host_inventory"
    VERIFY_DEPLOYMENTS = "verify_deployments"
    RECONCILE_SERVICES = "reconcile_services"
    START_EXACT_SERVICES = "start_exact_services"
    VERIFY_SERVICES_READY = "verify_services_ready"
    VERIFY_RUNTIME_QUALIFICATION = "verify_runtime_qualification"
    VERIFY_PARTICIPANT_IMPLEMENTATIONS = "verify_participant_implementations"
    VERIFY_PARTICIPANT_RUNTIMES = "verify_participant_runtimes"
    VERIFY_PARTICIPANT_BINDINGS = "verify_participant_bindings"
    RECONCILE_RUN = "reconcile_run"
    START_EXACT_RUN = "start_exact_run"
    FINAL_STATUS = "final_status"


@dataclass(frozen=True, slots=True)
class RuntimeStep:
    action: RuntimeAction
    mutating: bool
    reconcile_anchor: RuntimeAction | None = None
    failure_reconcile_anchor: RuntimeAction | None = None


@dataclass(frozen=True, slots=True)
class FrozenRuntimeManifest:
    release_digest: str
    prompt_generation_digest: str
    prompt_promotion_digest: str
    role_model_manifest_digest: str
    qualified_deployment_digests: tuple[str, ...]
    target_host_identity_digest: str
    participant_implementation_inventory_digest: str
    participant_runtime_inventory_digest: str
    participant_binding_manifest_digest: str
    experiment_spec_digest: str
    config_digests: tuple[tuple[str, str], ...]
    seed_identity: str

    def __post_init__(self) -> None:
        if not self.participant_implementation_inventory_digest.strip():
            raise ValueError("frozen runtime manifest requires implementation inventory digest")
        if not self.participant_runtime_inventory_digest.strip():
            raise ValueError("frozen runtime manifest requires participant runtime inventory digest")
        if not self.participant_binding_manifest_digest.strip():
            raise ValueError("frozen runtime manifest requires participant binding manifest digest")

    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class RuntimePlan:
    steps: tuple[RuntimeStep, ...]


def exact_runtime_plan() -> RuntimePlan:
    service_recovery = RuntimeAction.RECONCILE_SERVICES
    return RuntimePlan((
        RuntimeStep(RuntimeAction.VERIFY_RELEASE, False),
        RuntimeStep(RuntimeAction.VERIFY_PROMPT_PROMOTION, False),
        RuntimeStep(RuntimeAction.VERIFY_HOST_INVENTORY, False),
        RuntimeStep(RuntimeAction.VERIFY_DEPLOYMENTS, False),
        RuntimeStep(RuntimeAction.RECONCILE_SERVICES, False),
        RuntimeStep(RuntimeAction.START_EXACT_SERVICES, True, RuntimeAction.RECONCILE_SERVICES),
        RuntimeStep(RuntimeAction.VERIFY_SERVICES_READY, False, failure_reconcile_anchor=service_recovery),
        RuntimeStep(RuntimeAction.VERIFY_RUNTIME_QUALIFICATION, False, failure_reconcile_anchor=service_recovery),
        RuntimeStep(RuntimeAction.VERIFY_PARTICIPANT_IMPLEMENTATIONS, False),
        RuntimeStep(RuntimeAction.VERIFY_PARTICIPANT_RUNTIMES, False),
        RuntimeStep(RuntimeAction.VERIFY_PARTICIPANT_BINDINGS, False),
        RuntimeStep(RuntimeAction.RECONCILE_RUN, False),
        RuntimeStep(RuntimeAction.START_EXACT_RUN, True, RuntimeAction.RECONCILE_RUN),
        RuntimeStep(RuntimeAction.FINAL_STATUS, False, failure_reconcile_anchor=service_recovery),
    ))
