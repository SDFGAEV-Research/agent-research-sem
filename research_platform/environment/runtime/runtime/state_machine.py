from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import json

from research_platform.platform.kernel import (
    EffectCertainty,
    EffectClass,
    EffectReceipt,
    ExecutionContext,
    JsonValue,
    canonical_bytes,
    canonical_digest,
)

from ..api import (
    ActionIdentityViolation,
    ActionRequest,
    ActionResult,
    EnvironmentIdentity,
    EnvironmentImplementation,
    EnvironmentSession,
    Observation,
    StateMachineDynamicsPort,
    StateMachineEnvironmentSpec,
    StateTransition,
    action_request_digest,
    freeze_json_mapping,
    thaw_json_mapping,
)


class StateMachineCheckpointError(ValueError):
    """A state-machine checkpoint is malformed or belongs to another session."""


@dataclass(frozen=True, slots=True)
class _AppliedAction:
    request_digest: str
    result: ActionResult


@dataclass(frozen=True, slots=True)
class StateMachineEnvironmentImplementation(EnvironmentImplementation):
    spec: StateMachineEnvironmentSpec
    dynamics: StateMachineDynamicsPort

    def __post_init__(self) -> None:
        if self.dynamics.identity != self.spec.dynamics:
            raise ValueError("state-machine dynamics identity does not match the environment spec")

    @property
    def identity(self) -> EnvironmentIdentity:
        return EnvironmentIdentity(
            environment_id=self.spec.environment_id,
            implementation_version=self.spec.implementation_version,
            abi_version=self.spec.abi_version,
            schema_version=self.spec.schema_version,
            artifact_digest=self.spec.scientific_identity_digest(),
        )


class StateMachineEnvironmentSession(EnvironmentSession):
    """Exact, checkpointable session for deterministic non-open-world domains."""

    _CHECKPOINT_SCHEMA = "environment.state-machine.session.v1"

    def __init__(
        self,
        *,
        session_id: str,
        implementation: StateMachineEnvironmentImplementation,
    ) -> None:
        if not session_id.strip():
            raise ValueError("state-machine session_id must be non-empty")
        self.session_id = session_id
        self.implementation = implementation
        self.identity = implementation.identity
        self._provider_instance_id = f"{self.identity.environment_id}:{session_id}"
        self._state = freeze_json_mapping(
            implementation.spec.initial_state,
            field="initial_state",
        )
        self._observation_sequence = 0
        self._actions: dict[str, _AppliedAction] = {}
        self._closed = False

    @property
    def generation(self) -> str:
        return self.identity.artifact_digest

    def _assert_open(self) -> None:
        if self._closed:
            raise RuntimeError("state-machine environment session is closed")

    def _observation(
        self,
        *,
        kind: str,
        extra: Mapping[str, JsonValue] | None = None,
        artifact_refs: tuple[str, ...] = (),
    ) -> Observation:
        self._observation_sequence += 1
        state = thaw_json_mapping(self._state)
        return Observation(
            observation_id=(
                f"state-machine:{self.session_id}:observation:{self._observation_sequence}"
            ),
            generation=self.generation,
            payload={
                "kind": kind,
                "state": state,
                "state_digest": canonical_digest(state),
                **dict(extra or {}),
            },
            artifact_refs=artifact_refs,
        )

    def observe(self, context: ExecutionContext) -> Observation:
        del context
        self._assert_open()
        return self._observation(kind="state_machine_snapshot")

    def act(self, request: ActionRequest) -> ActionResult:
        self._assert_open()
        if request.action_type not in self.implementation.spec.action_types:
            raise ValueError(
                f"unsupported state-machine action type: {request.action_type}"
            )
        request_payload = thaw_json_mapping(
            freeze_json_mapping(request.payload, field="request.payload")
        )
        digest = action_request_digest(request)
        prior = self._actions.get(request.action_id)
        if prior is not None:
            if prior.request_digest != digest:
                raise ActionIdentityViolation(
                    f"state-machine action identity was reused with drift: {request.action_id}"
                )
            return prior.result

        transition = self.implementation.dynamics.transition(
            self._state,
            request,
            request.context,
        )
        if not isinstance(transition, StateTransition):
            raise TypeError("state-machine dynamics returned an invalid transition")
        next_state = freeze_json_mapping(transition.state, field="transition.state")
        if not transition.accepted and canonical_digest(next_state) != canonical_digest(self._state):
            raise ValueError("a rejected state-machine transition cannot mutate state")
        self._state = next_state
        certainty = (
            EffectCertainty.EFFECT_CONFIRMED
            if transition.accepted
            else EffectCertainty.EFFECT_REJECTED
        )
        effect = EffectReceipt(
            effect_id=f"state-machine-action:{request.action_id}",
            request_digest=digest,
            effect_class=EffectClass.IDEMPOTENT,
            certainty=certainty,
            provider_instance_id=self._provider_instance_id,
            verification_required=False,
            after_artifact=canonical_digest(self._state),
            provider_receipt=request.action_id,
        )
        observation = self._observation(
            kind="state_machine_transition",
            extra={
                "action": {
                    "action_id": request.action_id,
                    "action_type": request.action_type,
                    "payload": request_payload,
                },
                "accepted": transition.accepted,
                "transition_diagnostics": thaw_json_mapping(transition.diagnostics),
            },
            artifact_refs=transition.artifact_refs,
        )
        result = ActionResult(
            action_id=request.action_id,
            accepted=transition.accepted,
            observation=observation,
            effect=effect,
            diagnostics={
                "environment": "state_machine",
                "verified": True,
                "state_digest": effect.after_artifact,
                **thaw_json_mapping(transition.diagnostics),
            },
        )
        self._actions[request.action_id] = _AppliedAction(digest, result)
        return result

    def reconcile(self, effect: EffectReceipt, context: ExecutionContext) -> EffectReceipt:
        del context
        self._assert_open()
        action_id = effect.provider_receipt
        if not action_id or action_id not in self._actions:
            raise ActionIdentityViolation(
                "state-machine effect does not identify an applied session action"
            )
        applied = self._actions[action_id]
        if applied.request_digest != effect.request_digest:
            raise ActionIdentityViolation(
                "state-machine effect request digest does not match the action ledger"
            )
        authoritative = applied.result.effect
        if authoritative is None:
            raise RuntimeError("state-machine action ledger has no effect receipt")
        return replace(authoritative, verification_required=False)

    @staticmethod
    def _effect_document(effect: EffectReceipt) -> dict[str, object]:
        return {
            "effect_id": effect.effect_id,
            "request_digest": effect.request_digest,
            "effect_class": effect.effect_class.value,
            "certainty": effect.certainty.value,
            "provider_instance_id": effect.provider_instance_id,
            "verification_required": effect.verification_required,
            "before_artifact": effect.before_artifact,
            "after_artifact": effect.after_artifact,
            "provider_receipt": effect.provider_receipt,
        }

    @classmethod
    def _result_document(cls, result: ActionResult) -> dict[str, object]:
        observation = result.observation
        effect = result.effect
        return {
            "action_id": result.action_id,
            "accepted": result.accepted,
            "observation": None
            if observation is None
            else {
                "observation_id": observation.observation_id,
                "generation": observation.generation,
                "payload": observation.payload,
                "artifact_refs": observation.artifact_refs,
            },
            "effect": None if effect is None else cls._effect_document(effect),
            "diagnostics": result.diagnostics,
        }

    def checkpoint(self) -> bytes:
        self._assert_open()
        state = thaw_json_mapping(self._state)
        return canonical_bytes(
            {
                "schema_version": self._CHECKPOINT_SCHEMA,
                "session_id": self.session_id,
                "environment_generation": self.generation,
                "state": state,
                "state_digest": canonical_digest(state),
                "observation_sequence": self._observation_sequence,
                "actions": [
                    {
                        "action_id": action_id,
                        "request_digest": applied.request_digest,
                        "result": self._result_document(applied.result),
                    }
                    for action_id, applied in self._actions.items()
                ],
            }
        )

    def _decode_result(self, document: Mapping[str, JsonValue]) -> ActionResult:
        expected_fields = {"action_id", "accepted", "observation", "effect", "diagnostics"}
        if set(document) != expected_fields:
            raise StateMachineCheckpointError("checkpoint result schema is malformed")
        action_id = document["action_id"]
        accepted = document["accepted"]
        if not isinstance(action_id, str) or not action_id.strip() or not isinstance(accepted, bool):
            raise StateMachineCheckpointError("checkpoint result identity is malformed")
        observation_raw = document.get("observation")
        effect_raw = document.get("effect")
        observation = None
        if observation_raw is not None:
            if not isinstance(observation_raw, Mapping):
                raise StateMachineCheckpointError("checkpoint observation is malformed")
            if set(observation_raw) != {
                "observation_id",
                "generation",
                "payload",
                "artifact_refs",
            }:
                raise StateMachineCheckpointError("checkpoint observation schema is malformed")
            if not isinstance(observation_raw["payload"], Mapping):
                raise StateMachineCheckpointError("checkpoint observation payload is malformed")
            artifact_refs_raw = observation_raw["artifact_refs"]
            if (
                not isinstance(artifact_refs_raw, (list, tuple))
                or any(not isinstance(ref, str) or not ref.strip() for ref in artifact_refs_raw)
                or len(artifact_refs_raw) != len(set(artifact_refs_raw))
            ):
                raise StateMachineCheckpointError("checkpoint observation artifacts are malformed")
            observation = Observation(
                observation_id=observation_raw["observation_id"],
                generation=observation_raw["generation"],
                payload=thaw_json_mapping(
                    freeze_json_mapping(
                        observation_raw["payload"],
                        field="checkpoint.observation.payload",
                    )
                ),
                artifact_refs=tuple(artifact_refs_raw),
            )
            if (
                not isinstance(observation.observation_id, str)
                or not observation.observation_id.strip()
                or not isinstance(observation.generation, str)
            ):
                raise StateMachineCheckpointError("checkpoint observation identity is malformed")
            if observation.generation != self.generation:
                raise StateMachineCheckpointError("checkpoint observation generation drift")
        effect = None
        if effect_raw is not None:
            if not isinstance(effect_raw, Mapping):
                raise StateMachineCheckpointError("checkpoint effect is malformed")
            if set(effect_raw) != {
                "effect_id",
                "request_digest",
                "effect_class",
                "certainty",
                "provider_instance_id",
                "verification_required",
                "before_artifact",
                "after_artifact",
                "provider_receipt",
            }:
                raise StateMachineCheckpointError("checkpoint effect schema is malformed")
            if not isinstance(effect_raw["verification_required"], bool):
                raise StateMachineCheckpointError("checkpoint effect verification is malformed")
            required_effect_strings = (
                "effect_id",
                "request_digest",
                "effect_class",
                "certainty",
                "provider_instance_id",
                "after_artifact",
                "provider_receipt",
            )
            if any(
                not isinstance(effect_raw[name], str) or not effect_raw[name].strip()
                for name in required_effect_strings
            ):
                raise StateMachineCheckpointError("checkpoint effect identity is malformed")
            before_artifact = effect_raw["before_artifact"]
            if before_artifact is not None and (
                not isinstance(before_artifact, str) or not before_artifact.strip()
            ):
                raise StateMachineCheckpointError("checkpoint effect before artifact is malformed")
            effect = EffectReceipt(
                effect_id=effect_raw["effect_id"],
                request_digest=effect_raw["request_digest"],
                effect_class=EffectClass(str(effect_raw["effect_class"])),
                certainty=EffectCertainty(str(effect_raw["certainty"])),
                provider_instance_id=(
                    None
                    if effect_raw.get("provider_instance_id") is None
                    else effect_raw["provider_instance_id"]
                ),
                verification_required=effect_raw["verification_required"],
                before_artifact=(
                    None
                    if effect_raw.get("before_artifact") is None
                    else effect_raw["before_artifact"]
                ),
                after_artifact=(
                    None
                    if effect_raw.get("after_artifact") is None
                    else effect_raw["after_artifact"]
                ),
                provider_receipt=(
                    None
                    if effect_raw.get("provider_receipt") is None
                    else effect_raw["provider_receipt"]
                ),
            )
            if effect.provider_instance_id != self._provider_instance_id:
                raise StateMachineCheckpointError("checkpoint effect provider drift")
            if effect.effect_id != f"state-machine-action:{action_id}":
                raise StateMachineCheckpointError("checkpoint effect identity drift")
            if effect.provider_receipt != action_id:
                raise StateMachineCheckpointError("checkpoint effect receipt drift")
            if effect.effect_class is not EffectClass.IDEMPOTENT or effect.verification_required:
                raise StateMachineCheckpointError("checkpoint effect contract drift")
            if (
                len(effect.request_digest) != 64
                or effect.request_digest != effect.request_digest.lower()
                or any(char not in "0123456789abcdef" for char in effect.request_digest)
            ):
                raise StateMachineCheckpointError("checkpoint effect request digest is malformed")
            if (
                effect.after_artifact is None
                or len(effect.after_artifact) != 64
                or effect.after_artifact != effect.after_artifact.lower()
                or any(char not in "0123456789abcdef" for char in effect.after_artifact)
            ):
                raise StateMachineCheckpointError("checkpoint effect state digest is malformed")
            expected_certainty = (
                EffectCertainty.EFFECT_CONFIRMED
                if accepted
                else EffectCertainty.EFFECT_REJECTED
            )
            if effect.certainty is not expected_certainty:
                raise StateMachineCheckpointError("checkpoint effect certainty drift")
        diagnostics = document.get("diagnostics", {})
        if not isinstance(diagnostics, Mapping):
            raise StateMachineCheckpointError("checkpoint result diagnostics are malformed")
        restored_diagnostics = thaw_json_mapping(
            freeze_json_mapping(diagnostics, field="checkpoint.result.diagnostics")
        )
        return ActionResult(
            action_id=action_id,
            accepted=accepted,
            observation=observation,
            effect=effect,
            diagnostics=restored_diagnostics,
        )

    def restore(self, payload: bytes) -> None:
        self._assert_open()
        try:
            raw = json.loads(payload.decode("utf-8"))
            if not isinstance(raw, Mapping):
                raise TypeError("checkpoint root must be a mapping")
            if set(raw) != {
                "schema_version",
                "session_id",
                "environment_generation",
                "state",
                "state_digest",
                "observation_sequence",
                "actions",
            }:
                raise ValueError("checkpoint root schema mismatch")
            if raw["schema_version"] != self._CHECKPOINT_SCHEMA:
                raise ValueError("unsupported checkpoint schema")
            if raw["session_id"] != self.session_id:
                raise ValueError("checkpoint session identity mismatch")
            if raw["environment_generation"] != self.generation:
                raise ValueError("checkpoint environment generation mismatch")
            state_raw = raw["state"]
            if not isinstance(state_raw, Mapping):
                raise TypeError("checkpoint state must be a mapping")
            state = freeze_json_mapping(state_raw, field="checkpoint.state")
            if raw["state_digest"] != canonical_digest(state):
                raise ValueError("checkpoint state digest mismatch")
            sequence = raw["observation_sequence"]
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
                raise ValueError("checkpoint observation sequence is negative")
            action_rows = raw["actions"]
            if not isinstance(action_rows, list):
                raise TypeError("checkpoint actions must be a list")
            actions: dict[str, _AppliedAction] = {}
            for row in action_rows:
                if not isinstance(row, Mapping) or not isinstance(row.get("result"), Mapping):
                    raise TypeError("checkpoint action row is malformed")
                if set(row) != {"action_id", "request_digest", "result"}:
                    raise ValueError("checkpoint action row schema mismatch")
                action_id = row["action_id"]
                request_digest = row["request_digest"]
                if (
                    not isinstance(action_id, str)
                    or not action_id.strip()
                    or not isinstance(request_digest, str)
                    or len(request_digest) != 64
                    or request_digest != request_digest.lower()
                    or any(char not in "0123456789abcdef" for char in request_digest)
                    or action_id in actions
                ):
                    raise ValueError("checkpoint action identity is invalid")
                result = self._decode_result(row["result"])
                if result.action_id != action_id:
                    raise ValueError("checkpoint action/result identity mismatch")
                if result.effect is None or result.effect.request_digest != request_digest:
                    raise ValueError("checkpoint action/effect digest mismatch")
                if result.effect.provider_receipt != action_id:
                    raise ValueError("checkpoint action/effect receipt mismatch")
                actions[action_id] = _AppliedAction(request_digest, result)
            if sequence < len(actions):
                raise ValueError("checkpoint observation sequence precedes action ledger")
            observation_ids = tuple(
                applied.result.observation.observation_id
                for applied in actions.values()
                if applied.result.observation is not None
            )
            if len(observation_ids) != len(actions) or len(set(observation_ids)) != len(observation_ids):
                raise ValueError("checkpoint action observations are incomplete or duplicated")
            prefix = f"state-machine:{self.session_id}:observation:"
            for observation_id in observation_ids:
                if not observation_id.startswith(prefix):
                    raise ValueError("checkpoint action observation identity drift")
                observation_number = int(observation_id[len(prefix) :])
                if observation_number < 1 or observation_number > sequence:
                    raise ValueError("checkpoint action observation sequence is invalid")
            if actions:
                last_effect = next(reversed(actions.values())).result.effect
                if last_effect is None or last_effect.after_artifact != canonical_digest(state):
                    raise ValueError("checkpoint final state does not match the action ledger")
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            if isinstance(exc, StateMachineCheckpointError):
                raise
            raise StateMachineCheckpointError(
                "invalid or incompatible state-machine checkpoint"
            ) from exc
        self._state = state
        self._observation_sequence = sequence
        self._actions = actions

    def diagnostics(self) -> dict[str, object]:
        return {
            "environment": "state_machine",
            "session_id": self.session_id,
            "generation": self.generation,
            "closed": self._closed,
            "state_digest": canonical_digest(self._state),
            "observation_sequence": self._observation_sequence,
            "known_action_ids": len(self._actions),
        }

    def close(self) -> None:
        self._closed = True


class StateMachineEnvironmentRuntime:
    """Lifecycle owner for injected closed-world dynamics."""

    def open_session(
        self,
        implementation: object,
        *,
        session_id: str,
        services: object,
    ) -> StateMachineEnvironmentSession:
        del services
        if not isinstance(implementation, StateMachineEnvironmentImplementation):
            raise TypeError(
                "StateMachineEnvironmentRuntime requires StateMachineEnvironmentImplementation"
            )
        return StateMachineEnvironmentSession(
            session_id=session_id,
            implementation=implementation,
        )


__all__ = [
    "StateMachineCheckpointError",
    "StateMachineEnvironmentImplementation",
    "StateMachineEnvironmentRuntime",
    "StateMachineEnvironmentSession",
]
