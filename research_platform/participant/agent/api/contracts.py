from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from research_platform.participant.capability.api import CapabilityPort
from research_platform.platform.kernel import ExecutionContext


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    agent_id: str
    implementation_version: str
    abi_version: str
    schema_version: str
    artifact_digest: str = ""


@dataclass(frozen=True, slots=True)
class AgentSnapshot:
    agent_id: str
    implementation_version: str
    schema_version: str
    session_id: str
    payload_sha256: str
    opaque_payload: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class AgentTurnRequest:
    task: object
    context: ExecutionContext
    input_payload: object | None = None


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    output: object
    agent_generation: str | None = None
    artifacts: tuple[str, ...] = ()
    diagnostics: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class AgentSession(Protocol):
    """Generic agent session that can only see an abstract capability port."""

    def run_turn(self, request: AgentTurnRequest, capabilities: CapabilityPort) -> AgentTurnResult: ...
    def checkpoint(self) -> AgentSnapshot: ...
    def restore(self, snapshot: AgentSnapshot) -> None: ...
    def diagnostics(self) -> dict[str, object]: ...
    def close(self) -> None: ...


@runtime_checkable
class AgentImplementation(Protocol):
    """Scientific/behavioral agent implementation with no session lifecycle authority."""
    @property
    def identity(self) -> AgentIdentity: ...
