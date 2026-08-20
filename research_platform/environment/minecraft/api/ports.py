from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from research_platform.environment.runtime.api import (
    ActionReconciliationDisposition,
    ActionRequest,
    ActionResult,
    Observation,
)
from research_platform.platform.kernel import ExecutionContext

from .contracts import MinecraftObservationEvent


@dataclass(frozen=True, slots=True)
class MinecraftBridgeCommandResult:
    command: str
    acknowledged: bool
    verified: bool | None
    events: tuple[MinecraftObservationEvent, ...] = ()
    diagnostics: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MinecraftReconciliation:
    action_id: str
    disposition: ActionReconciliationDisposition
    observation: Observation | None = None
    diagnostics: Mapping[str, object] = field(default_factory=dict)


class MinecraftBridgePort(Protocol):
    """Bridge seam; the session does not depend on Mineflayer or Node."""

    def start(self) -> None: ...

    def command(
        self,
        command: str,
        payload: Mapping[str, object],
        *,
        timeout_s: float,
    ) -> MinecraftBridgeCommandResult: ...

    def reconcile_action(
        self,
        action_id: str,
        *,
        request: ActionRequest,
        context: ExecutionContext,
    ) -> MinecraftReconciliation: ...

    def close(self) -> None: ...


class MinecraftDiagnosticsPort(Protocol):
    """MC-owned diagnostic seam; storage and policy stay outside MC."""

    def event(
        self,
        *,
        phase: str,
        event: str,
        attributes: Mapping[str, object] | None = None,
        level: str = "DEBUG",
        correlation_refs: tuple[str, ...] = (),
    ) -> None: ...

    def failure(
        self,
        *,
        phase: str,
        code: str,
        message: str,
        exception: BaseException | None = None,
        attributes: Mapping[str, object] | None = None,
        correlation_refs: tuple[str, ...] = (),
    ) -> None: ...

    def metric(
        self,
        *,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> None: ...


class MinecraftCheckpointPort(Protocol):
    """World checkpoint seam; a client-state snapshot is not a world snapshot."""

    def capture(self, *, session_id: str, context: ExecutionContext | None) -> bytes: ...

    def restore(
        self,
        payload: bytes,
        *,
        session_id: str,
        context: ExecutionContext | None,
    ) -> None: ...


__all__ = [
    "MinecraftBridgeCommandResult",
    "MinecraftBridgePort",
    "MinecraftDiagnosticsPort",
    "MinecraftCheckpointPort",
    "MinecraftReconciliation",
]
