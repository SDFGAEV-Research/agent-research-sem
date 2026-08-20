from __future__ import annotations

from research_platform.execution.workflow.api import ScientificCycleExecution
from .contracts import AgentTurnOperationPort


class AgentTurnStudyWorkflow:
    """Generic Agent workflow with no Environment or Method assumptions."""

    workflow_id = "agent_turn.v1"
    surface_id = "agent_turn.operations.v1"
    configuration_digest = ""

    def run(
        self,
        operations: AgentTurnOperationPort,
        context,
        *,
        task: object,
        input_kind: str,
        input_payload: object,
    ) -> ScientificCycleExecution:
        result, rows = operations.agent_turn(
            task,
            {"input_kind": input_kind, "payload": input_payload},
            context,
        )
        final_context = (
            context.with_generation("agent", result.agent_generation)
            if result.agent_generation is not None
            else context
        )
        return ScientificCycleExecution(
            context_text=str(result.output),
            primary_result=result,
            final_context=final_context,
            operation_results=rows,
        )


__all__ = ["AgentTurnStudyWorkflow"]
