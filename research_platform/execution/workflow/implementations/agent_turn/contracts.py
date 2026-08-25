from __future__ import annotations

from typing import Protocol, runtime_checkable

from research_platform.participant.agent.api import AgentTurnResult
from research_platform.platform.kernel import ExecutionContext, JsonValue, OperationResult


@runtime_checkable
class AgentTurnOperationPort(Protocol):
    def agent_turn(
        self,
        task: object,
        input_payload: object,
        context: ExecutionContext,
    ) -> tuple[AgentTurnResult, tuple[OperationResult[JsonValue], ...]]: ...


__all__ = ["AgentTurnOperationPort"]
