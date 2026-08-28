from __future__ import annotations

from dataclasses import dataclass

import pytest

from projects.sem_paper.composition.minecraft_runtime_adapter import (
    MinecraftWorkloadEnvironmentAdapter,
    MinecraftWorkloadEnvironmentAdapterError,
)
from research_platform.environment.runtime.api import ActionResult, Observation
from research_platform.platform.kernel import ExecutionContext


@dataclass
class _Session:
    observed: object
    acted: ActionResult
    calls: list[tuple[str, str]]

    def observe(self, context):
        self.calls.append(("observe", context.task_id))
        return self.observed

    def act(self, request):
        self.calls.append((request.action_id, request.action_type))
        return self.acted


def _context() -> ExecutionContext:
    return ExecutionContext("run-1", "trace-1", "span-1", task_id="task-1")


def test_environment_adapter_preserves_state_and_verified_action_result() -> None:
    observed = Observation("obs-1", "env-1", {"state": {"health": 20}, "events": []})
    acted_observation = Observation("obs-2", "env-1", {"state": {"health": 19}, "events": []})
    session = _Session(
        observed,
        ActionResult("action-1", True, acted_observation, None, {"verified": True}),
        [],
    )
    adapter = MinecraftWorkloadEnvironmentAdapter(session)

    snapshot = adapter.observe(_context())
    result = adapter.act("action-1", "wait", {"ms": 1}, _context())

    assert snapshot.state == {"health": 20}
    assert snapshot.observation_id == "obs-1"
    assert result.accepted is True
    assert result.verified is True
    assert result.observation is not None
    assert result.observation.state == {"health": 19}


def test_environment_adapter_rejects_non_mapping_observation_without_fabricating_state() -> None:
    session = _Session(
        Observation("obs-1", "env-1", {"events": []}),
        ActionResult("action-1", True, None, None, {}),
        [],
    )
    with pytest.raises(MinecraftWorkloadEnvironmentAdapterError, match="missing state"):
        MinecraftWorkloadEnvironmentAdapter(session).observe(_context())
