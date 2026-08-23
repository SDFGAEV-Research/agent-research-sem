from __future__ import annotations

import base64
from collections import deque
from dataclasses import dataclass
import hashlib
import json
from typing import Mapping, Protocol

from research_platform.environment.runtime.api import (
    ActionIdentityViolation,
    ActionReconciliationDisposition,
    ActionRequest,
    ActionResult,
    EnvironmentIdentity,
    EnvironmentImplementation,
    EnvironmentSession,
    Observation,
    action_request_digest,
)
from research_platform.platform.kernel import (
    EffectCertainty,
    EffectClass,
    EffectReceipt,
    ExecutionContext,
    canonical_bytes,
    canonical_digest,
)

from ..api import MINECRAFT_ACTION_TYPES, MinecraftEnvironmentSpec, MinecraftSessionRuntimeIdentity
from ..api import MinecraftActionContractError, MinecraftObservationEvent, validate_minecraft_action
from ..api.ports import MinecraftBridgePort, MinecraftCheckpointPort, MinecraftDiagnosticsPort
from .state import MinecraftStateProjection


class MinecraftCheckpointUnavailable(RuntimeError):
    """The provider cannot prove a restorable Minecraft world checkpoint."""


class MinecraftEnvironmentFailure(RuntimeError):
    """A Minecraft provider failed at a named environment phase."""

    def __init__(
        self,
        phase: str,
        message: str,
        *,
        cause_code: str = "MINECRAFT_ENVIRONMENT_FAILURE",
        diagnostics: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(f"Minecraft environment phase {phase} failed: {message}")
        self.phase = phase
        self.cause_code = cause_code
        self.diagnostics = dict(diagnostics or {})


class MinecraftBridgeFactory(Protocol):
    def __call__(self, spec: MinecraftEnvironmentSpec) -> MinecraftBridgePort: ...


@dataclass(frozen=True, slots=True)
class _MinecraftActionVerification:
    request_digest: str
    accepted: bool
    verified: bool | None


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and value == value.lower()
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


@dataclass(frozen=True, slots=True)
class MinecraftEnvironmentImplementation(EnvironmentImplementation):
    """Scientific-independent MC implementation identity and provider selection."""

    spec: MinecraftEnvironmentSpec
    bridge_factory: MinecraftBridgeFactory
    checkpoint: MinecraftCheckpointPort | None = None

    @property
    def identity(self) -> EnvironmentIdentity:
        return EnvironmentIdentity(
            environment_id="minecraft",
            implementation_version=self.spec.implementation_version,
            abi_version=self.spec.abi_version,
            schema_version=self.spec.schema_version,
            artifact_digest=self.spec.scientific_identity_digest(),
        )


class MinecraftEnvironmentSession(EnvironmentSession):
    """MC session over the bridge seam and an optional authoritative world checkpoint."""

    _CHECKPOINT_SCHEMA = "minecraft-environment-session.v2"

    def __init__(
        self,
        *,
        session_id: str,
        implementation: MinecraftEnvironmentImplementation,
        bridge: MinecraftBridgePort,
        diagnostics: MinecraftDiagnosticsPort | None = None,
    ) -> None:
        if not session_id.strip():
            raise ValueError("Minecraft session_id must be non-empty")
        self.session_id = session_id
        self.implementation = implementation
        self.identity = implementation.identity
        self._provider_instance_id = f"{self.identity.environment_id}:{session_id}"
        self._bridge = bridge
        self._diagnostics = diagnostics
        self._closed = False
        self._observation_sequence = 0
        self._action_verifications: dict[str, _MinecraftActionVerification] = {}
        self._diagnostic_sink_failures: deque[str] = deque(maxlen=64)
        self._restore_faulted = False
        self._last_observation: Observation | None = None
        self._state = MinecraftStateProjection(max_entities=implementation.spec.max_entities)
        self._event_log("lifecycle", "MC_SESSION_START", level="INFO", attributes={"session_id": session_id})
        try:
            self._bridge.start()
        except Exception as exc:
            self._failure_log("start", exc)
            raise MinecraftEnvironmentFailure(
                "start",
                str(exc),
                cause_code=str(getattr(exc, "cause_code", "MINECRAFT_BRIDGE_START_FAILED")),
            ) from exc

    @property
    def generation(self) -> str:
        return self.identity.artifact_digest

    def _assert_open(self) -> None:
        if self._closed:
            raise RuntimeError("Minecraft environment session is closed")
        if self._restore_faulted:
            raise RuntimeError("Minecraft environment session is unusable after restore failure")

    def _event_log(
        self,
        phase: str,
        event: str,
        *,
        level: str = "DEBUG",
        attributes: Mapping[str, object] | None = None,
        correlation_refs: tuple[str, ...] = (),
    ) -> None:
        if self._diagnostics is None:
            return
        try:
            self._diagnostics.event(
                phase=phase,
                event=event,
                level=level,
                attributes={"session_id": self.session_id, **dict(attributes or {})},
                correlation_refs=correlation_refs,
            )
        except BaseException as exc:
            self._diagnostic_sink_failures.append(
                f"event:{phase}:{event}:{type(exc).__name__}:{exc}"
            )
            return

    def _failure_log(self, phase: str, exc: BaseException, *, code: str | None = None) -> None:
        if self._diagnostics is None:
            return
        try:
            self._diagnostics.failure(
                phase=phase,
                code=code or str(getattr(exc, "cause_code", "MINECRAFT_ENVIRONMENT_FAILURE")),
                message=str(exc),
                exception=exc,
                attributes={"session_id": self.session_id},
            )
        except BaseException as sink_exc:
            self._diagnostic_sink_failures.append(
                f"failure:{phase}:{type(sink_exc).__name__}:{sink_exc}"
            )
            return

    @staticmethod
    def _events_payload(events: tuple[object, ...]) -> list[dict[str, object]]:
        return [
            {
                "kind": event.kind,
                "payload": dict(event.payload),
                "sequence": event.sequence,
                "timestamp_ms": event.timestamp_ms,
                "source": event.source,
                "request_id": event.request_id,
            }
            for event in events
        ]

    def _ingest_events(
        self,
        events: tuple[MinecraftObservationEvent, ...],
        *,
        phase: str,
        refresh_entities: bool = False,
    ) -> None:
        try:
            if refresh_entities:
                self._state.replace_entities()
            for event in events:
                self._state.ingest(event)
        except Exception as exc:
            self._failure_log(f"{phase}.state", exc, code="MINECRAFT_STATE_PROJECTION_FAILED")
            raise MinecraftEnvironmentFailure(
                f"{phase}.state",
                str(exc),
                cause_code="MINECRAFT_STATE_PROJECTION_FAILED",
            ) from exc

    def _state_payload(self) -> dict[str, object]:
        return {
            "state": self._state.compact(),
            "state_digest": self._state.snapshot_digest(),
        }

    def _observation(
        self,
        *,
        payload: Mapping[str, object],
        artifact_refs: tuple[str, ...] = (),
    ) -> Observation:
        self._observation_sequence += 1
        observation = Observation(
            observation_id=f"minecraft:{self.session_id}:observation:{self._observation_sequence}",
            generation=self.generation,
            payload=dict(payload),
            artifact_refs=artifact_refs,
        )
        self._last_observation = observation
        return observation

    def observe(self, context: ExecutionContext) -> Observation:
        self._assert_open()
        self._event_log("observe", "MC_OBSERVE_START", attributes={"task_id": context.task_id})
        try:
            snapshot = self._bridge.command(
                "snapshot",
                {"context": {"run_id": context.run_id, "task_id": context.task_id}},
                timeout_s=self.implementation.spec.bridge.command_timeout_s,
            )
            if self._bridge.supports_command("observe_entities"):
                entities = self._bridge.command(
                    "observe_entities",
                    {"max_distance": 32, "limit": self.implementation.spec.max_entities},
                    timeout_s=self.implementation.spec.bridge.command_timeout_s,
                )
            else:
                error = MinecraftEnvironmentFailure(
                    "observe.entities",
                    "bridge does not declare observe_entities",
                    cause_code="MINECRAFT_ENTITY_OBSERVATION_UNAVAILABLE",
                )
                self._failure_log("observe.entities", error)
                raise error
        except Exception as exc:
            self._failure_log("observe", exc)
            raise MinecraftEnvironmentFailure(
                "observe",
                str(exc),
                cause_code=str(getattr(exc, "cause_code", "MINECRAFT_OBSERVE_FAILED")),
            ) from exc
        events = snapshot.events + entities.events
        if not any(event.kind in {"self_snapshot", "spawn_snapshot"} for event in events):
            error = MinecraftEnvironmentFailure(
                "observe",
                "bridge returned no self snapshot",
                cause_code="MINECRAFT_EMPTY_OBSERVATION",
            )
            self._failure_log("observe", error)
            raise error
        self._ingest_events(snapshot.events, phase="observe")
        self._ingest_events(entities.events, phase="observe.entities", refresh_entities=True)
        self._event_log("observe", "MC_OBSERVE_END", attributes={"event_count": len(events)})
        return self._observation(
            payload={
                "kind": "minecraft_snapshot",
                "events": self._events_payload(events),
                "bridge_diagnostics": {
                    "snapshot": dict(snapshot.diagnostics),
                    "entities": dict(entities.diagnostics),
                },
                **self._state_payload(),
            }
        )

    def _task_event(self, status: str, context: ExecutionContext) -> Observation:
        payload = {
            "task_id": str(context.task_id or ""),
            "status": status,
            "context": {
                "run_id": context.run_id,
                "study_id": context.study_id,
                "task_id": context.task_id,
            },
        }
        result = self._bridge.command(
            "task_event",
            payload,
            timeout_s=self.implementation.spec.bridge.command_timeout_s,
        )
        self._ingest_events(result.events, phase="task_event")
        return self._observation(
            payload={
                "kind": "minecraft_task_event",
                "events": self._events_payload(result.events),
                "bridge_diagnostics": dict(result.diagnostics),
                **self._state_payload(),
            }
        )

    def begin_task(self, metadata: Mapping[str, object], context: ExecutionContext) -> Observation:
        self._assert_open()
        del metadata
        return self._task_event("STARTED", context)

    def end_task(self, metadata: Mapping[str, object], context: ExecutionContext) -> Observation:
        self._assert_open()
        status = str(metadata.get("status") or "ENDED")
        return self._task_event(status, context)

    def act(self, request: ActionRequest) -> ActionResult:
        self._assert_open()
        request_digest = action_request_digest(request)
        prior = self._action_verifications.get(request.action_id)
        if prior is not None:
            if prior.request_digest != request_digest:
                raise ActionIdentityViolation(
                    f"Minecraft action identity was reused with drift: {request.action_id}"
                )
            raise ActionIdentityViolation(
                f"Minecraft action was already executed; reconcile its receipt: {request.action_id}"
            )
        self._event_log(
            "act",
            "MC_ACTION_START",
            attributes={"action_id": request.action_id, "action_type": request.action_type},
            correlation_refs=(request.action_id,),
        )
        if request.action_type not in MINECRAFT_ACTION_TYPES:
            raise ValueError(f"unsupported Minecraft action type: {request.action_type}")
        try:
            payload = validate_minecraft_action(request.action_type, request.payload)
        except MinecraftActionContractError as exc:
            self._failure_log("act.contract", exc, code=exc.code)
            raise MinecraftEnvironmentFailure("act.contract", str(exc), cause_code=exc.code) from exc
        payload.update(
            {
                "action_id": request.action_id,
                "context": {
                    "run_id": request.context.run_id,
                    "study_id": request.context.study_id,
                    "task_id": request.context.task_id,
                    "decision_cycle_id": request.context.decision_cycle_id,
                },
            }
        )
        try:
            result = self._bridge.command(
                request.action_type,
                payload,
                timeout_s=self.implementation.spec.bridge.command_timeout_s,
            )
        except Exception as exc:
            self._failure_log("act", exc)
            raise MinecraftEnvironmentFailure(
                "act",
                str(exc),
                cause_code=str(getattr(exc, "cause_code", "MINECRAFT_ACTION_FAILED")),
            ) from exc

        event_payload: Mapping[str, object] = {}
        for event in result.events:
            if event.kind == "action_result":
                event_payload = event.payload
                break
        self._ingest_events(
            result.events,
            phase="act",
            refresh_entities=request.action_type == "observe_entities",
        )
        verified = result.verified
        if verified is None and "verified" in event_payload:
            verified = bool(event_payload["verified"])
        accepted = bool(result.acknowledged)
        if result.diagnostics.get("error"):
            accepted = False
        certainty = (
            EffectCertainty.EFFECT_CONFIRMED
            if verified is True
            else EffectCertainty.EFFECT_REJECTED
            if verified is False and not accepted
            else EffectCertainty.EFFECT_POSSIBLE
        )
        receipt = EffectReceipt(
            effect_id=f"minecraft-action:{request.action_id}",
            request_digest=request_digest,
            effect_class=EffectClass.RECONCILABLE,
            certainty=certainty,
            provider_instance_id=self._provider_instance_id,
            verification_required=verified is not True,
            before_artifact=self._last_observation.observation_id if self._last_observation else None,
            after_artifact=canonical_digest(event_payload) if event_payload else None,
            provider_receipt=request.action_id,
        )
        self._action_verifications[request.action_id] = _MinecraftActionVerification(
            request_digest=request_digest,
            accepted=accepted,
            verified=verified,
        )
        self._event_log(
            "act",
            "MC_ACTION_END",
            level="INFO" if accepted else "WARNING",
            attributes={"action_id": request.action_id, "action_type": request.action_type, "verified": verified, "accepted": accepted},
            correlation_refs=(request.action_id,),
        )
        observation = self._observation(
            payload={
                "kind": "minecraft_action_result",
                "action_id": request.action_id,
                "action_type": request.action_type,
                "verified": verified,
                "events": self._events_payload(result.events),
                "bridge_diagnostics": dict(result.diagnostics),
                **self._state_payload(),
            }
        )
        return ActionResult(
            action_id=request.action_id,
            accepted=accepted,
            observation=observation,
            effect=receipt,
            diagnostics={
                "environment": "minecraft",
                "action_type": request.action_type,
                "verified": verified,
                "bridge_acknowledged": result.acknowledged,
            },
        )

    def reconcile(self, effect: EffectReceipt, context: ExecutionContext) -> EffectReceipt:
        self._assert_open()
        action_id = effect.provider_receipt
        if not action_id:
            raise MinecraftEnvironmentFailure("reconcile", "effect has no provider action identity")
        if effect.provider_instance_id != self._provider_instance_id:
            raise ActionIdentityViolation("Minecraft effect belongs to another environment provider")
        verification = self._action_verifications.get(action_id)
        if verification is not None and verification.request_digest != effect.request_digest:
            raise ActionIdentityViolation(
                "Minecraft effect request digest does not match the action ledger"
            )
        if verification is None or (
            verification.verified is not True
            and not (verification.verified is False and not verification.accepted)
        ):
            request = ActionRequest(action_id, "reconcile", {}, context)
            try:
                proof = self._bridge.reconcile_action(action_id, request=request, context=context)
            except Exception as exc:
                self._failure_log("reconcile", exc, code="MINECRAFT_RECONCILIATION_FAILED")
                raise MinecraftEnvironmentFailure(
                    "reconcile",
                    str(exc),
                    cause_code=str(getattr(exc, "cause_code", "MINECRAFT_RECONCILIATION_FAILED")),
                ) from exc
            disposition = proof.disposition
        elif verification.verified is True:
            disposition = ActionReconciliationDisposition.APPLIED
        else:
            disposition = (
                ActionReconciliationDisposition.NOT_APPLIED
            )
        if disposition is ActionReconciliationDisposition.UNKNOWN:
            self._failure_log("reconcile", RuntimeError("external action proof is unknown"), code="MINECRAFT_ACTION_PROOF_UNKNOWN")
            raise MinecraftEnvironmentFailure(
                "reconcile",
                "bridge cannot prove whether the external action was applied",
                cause_code="MINECRAFT_ACTION_PROOF_UNKNOWN",
            )
        certainty = (
            EffectCertainty.EFFECT_CONFIRMED
            if disposition is ActionReconciliationDisposition.APPLIED
            else EffectCertainty.EFFECT_REJECTED
        )
        return EffectReceipt(
            effect_id=effect.effect_id,
            request_digest=effect.request_digest,
            effect_class=effect.effect_class,
            certainty=certainty,
            provider_instance_id=effect.provider_instance_id,
            verification_required=False,
            before_artifact=effect.before_artifact,
            after_artifact=effect.after_artifact,
            provider_receipt=effect.provider_receipt,
        )

    def checkpoint(self) -> bytes:
        self._assert_open()
        provider = self.implementation.checkpoint
        if provider is None:
            self._event_log("checkpoint", "MC_CHECKPOINT_UNAVAILABLE", level="WARNING")
            raise MinecraftCheckpointUnavailable(
                "Minecraft session has no authoritative world checkpoint provider"
            )
        try:
            world_payload = provider.capture(session_id=self.session_id, context=None)
        except Exception as exc:
            self._failure_log("checkpoint", exc, code="MINECRAFT_CHECKPOINT_CAPTURE_FAILED")
            raise
        last_observation = self._last_observation
        payload = canonical_bytes(
            {
                "schema_version": self._CHECKPOINT_SCHEMA,
                "session_id": self.session_id,
                "environment_generation": self.generation,
                "world_payload_sha256": hashlib.sha256(world_payload).hexdigest(),
                "world_payload_base64": base64.b64encode(world_payload).decode("ascii"),
                "observation_sequence": self._observation_sequence,
                "actions": [
                    {
                        "action_id": action_id,
                        "request_digest": verification.request_digest,
                        "accepted": verification.accepted,
                        "verified": verification.verified,
                    }
                    for action_id, verification in sorted(self._action_verifications.items())
                ],
                "state": self._state.compact(),
                "state_digest": self._state.snapshot_digest(),
                "last_observation": None
                if last_observation is None
                else {
                    "observation_id": last_observation.observation_id,
                    "generation": last_observation.generation,
                    "payload": last_observation.payload,
                    "artifact_refs": last_observation.artifact_refs,
                },
            }
        )
        self._event_log(
            "checkpoint",
            "MC_CHECKPOINT_CAPTURED",
            level="INFO",
            attributes={"bytes": len(payload), "world_bytes": len(world_payload)},
        )
        return payload

    def restore(self, payload: bytes) -> None:
        self._assert_open()
        provider = self.implementation.checkpoint
        if provider is None:
            self._event_log("restore", "MC_RESTORE_UNAVAILABLE", level="WARNING")
            raise MinecraftCheckpointUnavailable(
                "Minecraft session has no authoritative world checkpoint provider"
            )
        try:
            document = json.loads(payload.decode("utf-8"))
            if not isinstance(document, Mapping):
                raise TypeError("checkpoint root must be a mapping")
            expected_fields = {
                "schema_version",
                "session_id",
                "environment_generation",
                "world_payload_sha256",
                "world_payload_base64",
                "observation_sequence",
                "actions",
                "state",
                "state_digest",
                "last_observation",
            }
            if set(document) != expected_fields:
                raise ValueError("Minecraft environment checkpoint schema fields mismatch")
            if document["schema_version"] != self._CHECKPOINT_SCHEMA:
                raise ValueError("unsupported Minecraft environment checkpoint schema")
            if document["session_id"] != self.session_id:
                raise ValueError("Minecraft environment checkpoint session mismatch")
            if document["environment_generation"] != self.generation:
                raise ValueError("Minecraft environment checkpoint generation mismatch")
            world_payload_base64 = document["world_payload_base64"]
            if not isinstance(world_payload_base64, str):
                raise TypeError("Minecraft world checkpoint payload encoding is invalid")
            world_payload = base64.b64decode(world_payload_base64, validate=True)
            world_payload_sha256 = document["world_payload_sha256"]
            if not _is_sha256(world_payload_sha256):
                raise TypeError("Minecraft world checkpoint payload digest is invalid")
            if hashlib.sha256(world_payload).hexdigest() != world_payload_sha256:
                raise ValueError("Minecraft world checkpoint payload digest mismatch")
            state_raw = document["state"]
            if not isinstance(state_raw, Mapping):
                raise TypeError("Minecraft checkpoint state must be a mapping")
            restored_state = MinecraftStateProjection.from_compact(
                state_raw,
                max_entities=self.implementation.spec.max_entities,
            )
            state_digest = document["state_digest"]
            if not _is_sha256(state_digest):
                raise TypeError("Minecraft state checkpoint digest is invalid")
            if restored_state.snapshot_digest() != state_digest:
                raise ValueError("Minecraft state checkpoint digest mismatch")
            observation_sequence = document["observation_sequence"]
            if (
                isinstance(observation_sequence, bool)
                or not isinstance(observation_sequence, int)
                or observation_sequence < 0
            ):
                raise ValueError("Minecraft checkpoint observation sequence is invalid")
            action_rows = document["actions"]
            if not isinstance(action_rows, list):
                raise ValueError("Minecraft checkpoint actions must be a list")
            restored_actions: dict[str, _MinecraftActionVerification] = {}
            for row in action_rows:
                if not isinstance(row, Mapping):
                    raise ValueError("Minecraft checkpoint action row is invalid")
                action_id = row.get("action_id")
                request_digest = row.get("request_digest")
                accepted = row.get("accepted")
                verified = row.get("verified")
                if (
                    set(row) != {"action_id", "request_digest", "accepted", "verified"}
                    or not isinstance(action_id, str)
                    or not action_id.strip()
                    or action_id in restored_actions
                    or not _is_sha256(request_digest)
                    or not isinstance(accepted, bool)
                    or (verified is not None and not isinstance(verified, bool))
                ):
                    raise ValueError("Minecraft checkpoint action identity set is invalid")
                restored_actions[action_id] = _MinecraftActionVerification(
                    request_digest=request_digest,
                    accepted=accepted,
                    verified=verified,
                )
            last_raw = document["last_observation"]
            restored_last = None
            if last_raw is not None:
                if not isinstance(last_raw, Mapping):
                    raise TypeError("Minecraft checkpoint last observation is invalid")
                if set(last_raw) != {
                    "observation_id",
                    "generation",
                    "payload",
                    "artifact_refs",
                }:
                    raise ValueError("Minecraft checkpoint observation schema mismatch")
                observation_id = last_raw["observation_id"]
                observation_generation = last_raw["generation"]
                if not isinstance(last_raw["payload"], Mapping):
                    raise TypeError("Minecraft checkpoint observation payload is invalid")
                artifact_refs = last_raw["artifact_refs"]
                if (
                    not isinstance(observation_id, str)
                    or not observation_id.strip()
                    or not isinstance(observation_generation, str)
                    or not isinstance(artifact_refs, list)
                    or any(
                        not isinstance(ref, str) or not ref.strip()
                        for ref in artifact_refs
                    )
                    or len(artifact_refs) != len(set(artifact_refs))
                ):
                    raise TypeError("Minecraft checkpoint observation identity is invalid")
                restored_last = Observation(
                    observation_id=observation_id,
                    generation=observation_generation,
                    payload=last_raw["payload"],
                    artifact_refs=tuple(artifact_refs),
                )
                if restored_last.generation != self.generation:
                    raise ValueError("Minecraft checkpoint observation generation mismatch")
                expected_observation_id = (
                    f"minecraft:{self.session_id}:observation:{observation_sequence}"
                )
                if restored_last.observation_id != expected_observation_id:
                    raise ValueError("Minecraft checkpoint observation sequence mismatch")
            if (observation_sequence == 0) != (restored_last is None):
                raise ValueError("Minecraft checkpoint last observation cardinality mismatch")
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            self._failure_log("restore.decode", exc, code="MINECRAFT_CHECKPOINT_INVALID")
            raise MinecraftEnvironmentFailure(
                "restore.decode",
                str(exc),
                cause_code="MINECRAFT_CHECKPOINT_INVALID",
            ) from exc

        bridge_stopped = False
        try:
            self._bridge.close()
            bridge_stopped = True
            provider.restore(world_payload, session_id=self.session_id, context=None)
            self._bridge.start()
            bridge_stopped = False
        except Exception as exc:
            self._restore_faulted = True
            recovery_error: BaseException | None = None
            if bridge_stopped:
                try:
                    self._bridge.start()
                except BaseException as recovery_exc:
                    recovery_error = recovery_exc
            detail = str(exc)
            if recovery_error is not None:
                detail += (
                    "; bridge recovery failed: "
                    f"{type(recovery_error).__name__}: {recovery_error}"
                )
            self._failure_log("restore", exc, code="MINECRAFT_CHECKPOINT_RESTORE_FAILED")
            raise MinecraftEnvironmentFailure(
                "restore",
                detail,
                cause_code="MINECRAFT_CHECKPOINT_RESTORE_FAILED",
                diagnostics={
                    "bridge_recovery_failed": recovery_error is not None,
                },
            ) from exc
        self._state = restored_state
        self._observation_sequence = observation_sequence
        self._action_verifications = restored_actions
        self._last_observation = restored_last
        self._event_log(
            "restore",
            "MC_CHECKPOINT_RESTORED",
            level="INFO",
            attributes={"bytes": len(payload), "world_bytes": len(world_payload)},
        )

    def diagnostics(self) -> dict[str, object]:
        return {
            "environment": "minecraft",
            "session_id": self.session_id,
            "generation": self.generation,
            "closed": self._closed,
            "observation_sequence": self._observation_sequence,
            "known_action_ids": len(self._action_verifications),
            "diagnostic_sink_failures": tuple(self._diagnostic_sink_failures),
            "restore_faulted": self._restore_faulted,
            "checkpoint_provider": self.implementation.checkpoint is not None,
            "state_digest": self._state.snapshot_digest(),
            "state_last_event_sequence": self._state.last_event_sequence,
            "state_entity_count": len(self._state.entities),
        }

    def close(self) -> None:
        if self._closed:
            return
        self._event_log("lifecycle", "MC_SESSION_CLOSE", level="INFO")
        try:
            self._bridge.close()
        except Exception as exc:
            self._failure_log("close", exc, code="MINECRAFT_BRIDGE_CLOSE_FAILED")
            raise MinecraftEnvironmentFailure(
                "close",
                str(exc),
                cause_code="MINECRAFT_BRIDGE_CLOSE_FAILED",
            ) from exc
        self._closed = True


class MinecraftEnvironmentRuntime:
    """Session lifecycle owner; it does not own MC semantics or server lifecycle."""

    RUNTIME_ID = "minecraft.environment.session"
    RUNTIME_VERSION = "2"
    RUNTIME_ABI_VERSION = "1"

    def __init__(
        self,
        bridge_factory: MinecraftBridgeFactory,
        *,
        diagnostics: MinecraftDiagnosticsPort | None = None,
    ) -> None:
        self._bridge_factory = bridge_factory
        self._diagnostics = diagnostics
        self._runtime_identity = MinecraftSessionRuntimeIdentity(
            self.RUNTIME_ID,
            self.RUNTIME_VERSION,
            self.RUNTIME_ABI_VERSION,
            canonical_digest(
                {
                    "runtime_id": self.RUNTIME_ID,
                    "runtime_version": self.RUNTIME_VERSION,
                    "runtime_abi_version": self.RUNTIME_ABI_VERSION,
                    "session_contract": MinecraftEnvironmentSession._CHECKPOINT_SCHEMA,
                }
            ),
        )

    @property
    def runtime_identity(self) -> MinecraftSessionRuntimeIdentity:
        return self._runtime_identity

    def open_session(
        self,
        implementation: object,
        *,
        session_id: str,
        services: object,
    ) -> MinecraftEnvironmentSession:
        del services
        if not isinstance(implementation, MinecraftEnvironmentImplementation):
            raise TypeError("MinecraftEnvironmentRuntime requires MinecraftEnvironmentImplementation")
        bridge = self._bridge_factory(implementation.spec)
        return MinecraftEnvironmentSession(
            session_id=session_id,
            implementation=implementation,
            bridge=bridge,
            diagnostics=self._diagnostics,
        )


__all__ = [
    "MinecraftBridgeFactory",
    "MinecraftCheckpointUnavailable",
    "MinecraftEnvironmentFailure",
    "MinecraftEnvironmentImplementation",
    "MinecraftEnvironmentRuntime",
    "MinecraftEnvironmentSession",
]
