from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from threading import RLock
from typing import Mapping, Protocol, runtime_checkable

from research_platform.platform.kernel import ExecutionContext


@dataclass(frozen=True, slots=True)
class MethodObservation:
    observation_id: str
    context: ExecutionContext
    method_id: str
    session_id: str
    kind: str
    payload: Mapping[str, object]

    @classmethod
    def build(cls, context: ExecutionContext, method_id: str, session_id: str, kind: str, payload: Mapping[str, object]) -> "MethodObservation":
        document = {
            "context": asdict(context),
            "method_id": method_id,
            "session_id": session_id,
            "kind": kind,
            "payload": dict(payload),
        }
        raw = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return cls(f"methodobs_{hashlib.sha256(raw).hexdigest()[:24]}", context, method_id, session_id, kind, dict(payload))


class MethodObservationDeliveryError(RuntimeError):
    def __init__(self, observation: MethodObservation, cause: BaseException) -> None:
        super().__init__(f"method observation delivery failed after scientific mutation commit: {observation.observation_id}: {cause}")
        self.observation = observation
        self.cause = cause
        self.mutation_committed = True
        self.recommended_recovery = "replay_observation"


@runtime_checkable
class MethodObservationSink(Protocol):
    def record(self, observation: MethodObservation) -> object: ...


@runtime_checkable
class MethodObservationOutboxPort(Protocol):
    """Method-facing durable handoff boundary for committed observations."""

    def restore(self, observations: tuple[MethodObservation, ...]) -> None: ...
    def snapshot(self) -> tuple[MethodObservation, ...]: ...
    def pending_count(self) -> int: ...
    def deliver(self, observation: MethodObservation) -> None: ...
    def flush(self) -> tuple[str, ...]: ...


@runtime_checkable
class MethodObservationOutboxFactoryPort(Protocol):
    """Creates an outbox without exposing the participant runtime implementation."""

    def create(self, sink: MethodObservationSink) -> MethodObservationOutboxPort: ...


@dataclass(frozen=True, slots=True)
class MethodServices:
    observation_sink: MethodObservationSink
