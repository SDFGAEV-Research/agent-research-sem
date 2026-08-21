"""Immutable identity of one exact experiment/run launch."""

from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import canonical_digest


@dataclass(frozen=True, slots=True, order=True)
class CompositionPlanReference:
    """The identity and digest of one composition plan frozen into a run.

    The launch manifest records composition provenance as immutable metadata;
    it does not embed providers or expose a capability resolver.
    """

    composition_id: str
    owner_key: str
    scope_key: str
    plan_digest: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.composition_id, self.owner_key, self.scope_key)):
            raise ValueError("composition plan reference identity is incomplete")
        if len(self.plan_digest) != 64 or any(character not in "0123456789abcdef" for character in self.plan_digest.lower()):
            raise ValueError("composition plan reference digest must be SHA-256")


@dataclass(frozen=True, slots=True)
class RunLaunchManifest:
    """Single frozen launch authority for experiment, runtime, and recovery.

    This record joins release, prompt, model, host, participant, experiment,
    command, configuration, seed, and composition-plan identities. Runtime
    control consumes it; it does not own a second manifest shape.
    """

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
    command_argv: tuple[str, ...]
    launcher_binary_sha256: str
    command_environment_digest: str
    config_digests: tuple[tuple[str, str], ...]
    seed_identity: str
    composition_plans: tuple[CompositionPlanReference, ...]

    def __post_init__(self) -> None:
        required = (
            self.release_digest,
            self.prompt_generation_digest,
            self.prompt_promotion_digest,
            self.role_model_manifest_digest,
            self.target_host_identity_digest,
            self.participant_implementation_inventory_digest,
            self.participant_runtime_inventory_digest,
            self.participant_binding_manifest_digest,
            self.experiment_spec_digest,
            self.seed_identity,
        )
        if any(not value.strip() for value in required):
            raise ValueError("run launch manifest identity is incomplete")
        if not self.command_argv or not self.command_argv[0].strip():
            raise ValueError("run launch manifest command argv is required")
        for field_name, digest in (
            ("launcher binary", self.launcher_binary_sha256),
            ("command environment", self.command_environment_digest),
        ):
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
                raise ValueError(f"run launch manifest {field_name} digest must be SHA-256")
        if len(self.qualified_deployment_digests) != len(set(self.qualified_deployment_digests)):
            raise ValueError("run launch manifest has duplicate deployment digests")
        config_names = tuple(name for name, _ in self.config_digests)
        if any(not name.strip() or not digest.strip() for name, digest in self.config_digests):
            raise ValueError("run launch manifest configuration identity is incomplete")
        if len(config_names) != len(set(config_names)):
            raise ValueError("run launch manifest has duplicate configuration identities")
        if not self.composition_plans:
            raise ValueError("run launch manifest requires at least one composition plan")
        ordered = tuple(sorted(self.composition_plans))
        if self.composition_plans != ordered:
            raise ValueError("run launch manifest composition plans must be canonically ordered")
        composition_keys = tuple(
            (row.composition_id, row.owner_key, row.scope_key)
            for row in self.composition_plans
        )
        if len(composition_keys) != len(set(composition_keys)):
            raise ValueError("run launch manifest has duplicate composition plan identities")

    @property
    def composition_plan_digest(self) -> str:
        """Aggregate all frozen composition evidence into one run identity field."""

        return canonical_digest(self.composition_plans)

    def digest(self) -> str:
        return canonical_digest(self)


__all__ = ["CompositionPlanReference", "RunLaunchManifest"]
