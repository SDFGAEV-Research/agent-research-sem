from __future__ import annotations

import pytest

from research_platform.experimentation.experiment.runtime import ExperimentWorkflowSurfaceRegistry


def test_unknown_workflow_surface_fails_without_constructing_scientific_operations():
    registry = ExperimentWorkflowSurfaceRegistry(())
    with pytest.raises(LookupError):
        registry.bind("future.unknown.surface", object())


def test_builtin_workflows_declare_distinct_narrow_surfaces():
    from research_platform.execution.workflow.implementations.agent_turn.agent_turn_workflow import AgentTurnStudyWorkflow
    from research_platform.execution.workflow.implementations.context_action.context_action_workflow import ContextActionStudyWorkflow

    assert AgentTurnStudyWorkflow.surface_id == "agent_turn.operations.v1"
    assert ContextActionStudyWorkflow.surface_id == "context_action.operations.v1"
    assert AgentTurnStudyWorkflow.surface_id != ContextActionStudyWorkflow.surface_id
