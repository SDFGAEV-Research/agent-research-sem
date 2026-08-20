from __future__ import annotations

from typing import Protocol, runtime_checkable

from research_platform.participant.agent.api import AgentTurnResult
from research_platform.platform.kernel import ExecutionContext, OperationResult


@runtime_checkable
class AgentTurnOperationPort(Protocol):
    def agent_turn(
        self,
        task: object,
        input_payload: object,
        context: ExecutionContext,
    ) -> tuple[AgentTurnResult, tuple[OperationResult[object], ...]]: ...


__all__ = ["AgentTurnOperationPort"]
