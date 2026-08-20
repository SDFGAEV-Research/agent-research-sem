from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from research_platform.environment.runtime.api import (
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
    canonical_digest,
)

from ..api import MINECRAFT_ACTION_TYPES, MinecraftEnvironmentSpec, MinecraftSessionRuntimeIdentity
from ..api.ports import MinecraftBridgePort, MinecraftCheckpointPort, MinecraftDiagnosticsPort


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
            artifact_digest=canonical_digest(self.spec),
        )


class MinecraftEnvironmentSession(EnvironmentSession):
    """MC session over the bridge seam and an optional authoritative world checkpoint."""

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
        self._bridge = bridge
        self._diagnostics = diagnostics
        self._closed = False
        self._observation_sequence = 0
        self._last_action_ids: set[str] = set()
        self._last_observation: Observation | None = None
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
        except BaseException:
            # The environment result must not be replaced by a telemetry sink
            # failure; the composition adapter records sink failures separately.
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
        except BaseException:
            return

    @staticmethod
    def _events_payload(events: tuple[object, ...]) -> list[dict[str, object]]:
        return [
            {
                "kind": event.kind,
                "payload": dict(event.payload),
                "sequence": event.sequence,
            }
            for event in events
        ]

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
            result = self._bridge.command(
                "snapshot",
                {"context": {"run_id": context.run_id, "task_id": context.task_id}},
                timeout_s=self.implementation.spec.bridge.command_timeout_s,
            )
        except Exception as exc:
            self._failure_log("observe", exc)
            raise MinecraftEnvironmentFailure(
                "observe",
                str(exc),
                cause_code=str(getattr(exc, "cause_code", "MINECRAFT_OBSERVE_FAILED")),
            ) from exc
        self._event_log("observe", "MC_OBSERVE_END", attributes={"event_count": len(result.events)})
        return self._observation(
            payload={
                "kind": "minecraft_snapshot",
                "events": self._events_payload(result.events),
                "bridge_diagnostics": dict(result.diagnostics),
            }
        )

    def act(self, request: ActionRequest) -> ActionResult:
        self._assert_open()
        self._event_log(
            "act",
            "MC_ACTION_START",
            attributes={"action_id": request.action_id, "action_type": request.action_type},
            correlation_refs=(request.action_id,),
        )
        if request.action_type not in MINECRAFT_ACTION_TYPES:
            raise ValueError(f"unsupported Minecraft action type: {request.action_type}")
        if not isinstance(request.payload, Mapping):
            raise TypeError("Minecraft action payload must be a mapping")
        payload = dict(request.payload)
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
        request_digest = action_request_digest(request)
        receipt = EffectReceipt(
            effect_id=f"minecraft-action:{request.action_id}",
            request_digest=request_digest,
            effect_class=EffectClass.RECONCILABLE,
            certainty=certainty,
            provider_instance_id=self.identity.environment_id,
            verification_required=verified is not True,
            before_artifact=self._last_observation.observation_id if self._last_observation else None,
            after_artifact=canonical_digest(event_payload) if event_payload else None,
            provider_receipt=request.action_id,
        )
        self._last_action_ids.add(request.action_id)
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
        if proof.disposition is ActionReconciliationDisposition.UNKNOWN:
            self._failure_log("reconcile", RuntimeError("external action proof is unknown"), code="MINECRAFT_ACTION_PROOF_UNKNOWN")
            raise MinecraftEnvironmentFailure(
                "reconcile",
                "bridge cannot prove whether the external action was applied",
                cause_code="MINECRAFT_ACTION_PROOF_UNKNOWN",
            )
        certainty = (
            EffectCertainty.EFFECT_CONFIRMED
            if proof.disposition is ActionReconciliationDisposition.APPLIED
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
            payload = provider.capture(session_id=self.session_id, context=None)
        except Exception as exc:
            self._failure_log("checkpoint", exc, code="MINECRAFT_CHECKPOINT_CAPTURE_FAILED")
            raise
        self._event_log("checkpoint", "MC_CHECKPOINT_CAPTURED", level="INFO", attributes={"bytes": len(payload)})
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
            provider.restore(payload, session_id=self.session_id, context=None)
        except Exception as exc:
            self._failure_log("restore", exc, code="MINECRAFT_CHECKPOINT_RESTORE_FAILED")
            raise
        self._event_log("restore", "MC_CHECKPOINT_RESTORED", level="INFO", attributes={"bytes": len(payload)})

    def diagnostics(self) -> dict[str, object]:
        return {
            "environment": "minecraft",
            "session_id": self.session_id,
            "generation": self.generation,
            "closed": self._closed,
            "observation_sequence": self._observation_sequence,
            "known_action_ids": len(self._last_action_ids),
            "checkpoint_provider": self.implementation.checkpoint is not None,
        }

    def close(self) -> None:
        if self._closed:
            return
        self._event_log("lifecycle", "MC_SESSION_CLOSE", level="INFO")
        self._closed = True
        self._bridge.close()


class MinecraftEnvironmentRuntime:
    """Session lifecycle owner; it does not own MC semantics or server lifecycle."""

    RUNTIME_ID = "minecraft.environment.session"
    RUNTIME_VERSION = "1"
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
                    "session_contract": "minecraft-environment-session.v1",
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
