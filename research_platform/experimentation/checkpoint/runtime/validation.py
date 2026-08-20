from __future__ import annotations

from research_platform.platform.kernel import canonical_digest

from ..api.contracts import RunCheckpointBundle
from research_platform.participant.core.api import BoundParticipants
from research_platform.execution.decision.cycle_identity import DecisionCycleIdentity
from research_platform.experimentation.experiment.api import ExperimentSpec


class RunCheckpointIdentityMismatch(RuntimeError):
    pass


def validate_restore_bundle(
    bundle: RunCheckpointBundle,
    *,
    spec: ExperimentSpec,
    bound: BoundParticipants,
    cycle_identity: DecisionCycleIdentity,
) -> RunCheckpointBundle:
    manifest = bundle.manifest
    expected_identity = (
        spec.identity_digest(),
        cycle_identity.run_id,
        cycle_identity.session_id,
        cycle_identity.decision_cycle_id,
        cycle_identity.digest(),
    )
    actual_identity = (
        manifest.experiment_spec_digest,
        manifest.run_id,
        manifest.session_id,
        manifest.decision_cycle_id,
        manifest.cycle_identity_digest,
    )
    if actual_identity != expected_identity:
        raise RunCheckpointIdentityMismatch(
            f"checkpoint treatment/runtime identity mismatch: expected={expected_identity!r} actual={actual_identity!r}"
        )

    expected_participants = {
        row.role: (
            row.runtime.binding.digest(),
            canonical_digest(row.component),
        )
        for row in bound.participants
    }
    actual_participants = {
        row.role: (row.checkpoint.runtime_binding_digest, row.checkpoint.component_digest)
        for row in manifest.participant_snapshots
    }
    if actual_participants != expected_participants:
        raise RunCheckpointIdentityMismatch(
            f"checkpoint participant topology mismatch: expected={expected_participants!r} actual={actual_participants!r}"
        )

    payloads = {row.ref.role: row for row in bundle.participant_payloads}
    if set(payloads) != set(actual_participants):
        raise RunCheckpointIdentityMismatch("checkpoint participant payload set does not match manifest")
    bound_by_role = {row.role: row for row in bound.participants}
    for role, item in payloads.items():
        participant = bound_by_role[role]
        try:
            item.checkpoint.verify(
                binding=participant.runtime.binding,
                component=participant.component,
                session_id=cycle_identity.session_id,
            )
        except RuntimeError as exc:
            raise RunCheckpointIdentityMismatch(str(exc)) from exc
    return bundle


__all__ = ["RunCheckpointIdentityMismatch", "validate_restore_bundle"]
