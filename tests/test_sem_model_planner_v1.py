from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from projects.sem_paper.composition import (
    SemPaperModelPlanner,
    SemPaperModelPlannerBinding,
    SemPaperModelPlannerError,
    SemPaperModelPlannerFactory,
)
from projects.sem_paper.composition.minecraft_workload import MinecraftTaskSpec
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from research_platform.model.request.runtime import (
    DirectoryContentAddressedStore,
    DirectoryModelRequestLedger,
    ReconstructableModelRequestRecorder,
)
from research_platform.model.request.prompt.runtime import (
    PromptRegistry,
    default_block_policies,
    default_output_schemas,
    default_prompt_specs,
)
from research_platform.model.request.prompt.composition import FrozenPromptRequestBinding
from research_platform.model.serving.endpoint import ModelEndpointResponse
from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity


class RecordingEndpoint:
    def __init__(self, text: str) -> None:
        self.text = text
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return ModelEndpointResponse(
            request_id=request.request.request_id,
            deployment_id=request.deployment_id,
            text=self.text,
            output_tokens=7,
        )


def _factory(root: Path, endpoint: RecordingEndpoint, registry: PromptRegistry | None = None):
    registry = registry or PromptRegistry()
    if registry.generation == "empty":
        registry.publish("planner-generation-1", default_prompt_specs())
    prompt_binding = FrozenPromptRequestBinding(
        registry=registry,
        prompt_id="planner.v6",
        policy=default_block_policies()["planner"],
        schemas=default_output_schemas(),
        model_requests=ReconstructableModelRequestRecorder(
            DirectoryContentAddressedStore(root / "blobs"),
            DirectoryModelRequestLedger(root / "requests"),
        ),
    )
    return SemPaperModelPlannerFactory(SemPaperModelPlannerBinding(
        prompt_requests=prompt_binding,
        body_builder=SemPaperModelPlanner.body,
        model=ImmutableModelIdentity("planner", "qwen", "revision-1", "sglang", "1", "bfloat16", None, 262144),
        deployment_id="planner-deployment",
        deployment_generation="d" * 64,
        context_length=262144,
        endpoint=endpoint,
    ))


def _decide(factory, task=None):
    planner = factory.create(
        role=BranchRole.CONTROL,
        candidate=None,
        task=task or MinecraftTaskSpec("task-1", "collection", "collect oak logs"),
        method=object(),
    )
    return planner.decide(
        task=task or MinecraftTaskSpec("task-1", "collection", "collect oak logs"),
        context=ExecutionContext("run-1", "trace-1", "span-1", branch_id="control", decision_cycle_id="cycle-1"),
        state={"inventory": {}, "position": {"x": 0, "y": 64, "z": 0}},
        memory_context="previously found oak near spawn",
        step=0,
        prior_actions=(),
    )


def test_model_planner_freezes_prompt_generation_and_binds_exact_request() -> None:
    with tempfile.TemporaryDirectory() as td:
        registry = PromptRegistry()
        registry.publish("planner-generation-1", default_prompt_specs())
        endpoint = RecordingEndpoint(json.dumps({
            "action_type": "collect_block",
            "arguments": {"block": "oak_log", "count": 1},
            "completion_claim": False,
        }))
        factory = _factory(Path(td), endpoint, registry)
        registry.publish("planner-generation-2", default_prompt_specs())

        decision = _decide(factory)

        assert decision.action_type == "collect_block"
        assert decision.payload["max_distance"] == 48.0
        assert len(endpoint.requests) == 1
        request = endpoint.requests[0]
        assert request.request.prompt_generation_id == "planner-generation-1"
        assert request.deployment_id == "planner-deployment"
        assert request.deployment_generation == "d" * 64
        assert request.body["messages"][0]["role"] == "user"
        assert request.body["chat_template_kwargs"] == {"enable_thinking": False}
        assert request.body["response_format"] == {"type": "json_object"}


def test_model_planner_rejects_unknown_fields_and_does_not_emit_an_action() -> None:
    with tempfile.TemporaryDirectory() as td:
        endpoint = RecordingEndpoint(json.dumps({
            "action_type": "collect_block",
            "arguments": {"block": "oak_log"},
            "completion_claim": False,
            "rationale": "extra field is not in the frozen schema",
        }))
        factory = _factory(Path(td), endpoint)
        with pytest.raises(SemPaperModelPlannerError, match="fields"):
            _decide(factory)


def test_model_planner_rejects_action_contract_violation_at_decision_boundary() -> None:
    with tempfile.TemporaryDirectory() as td:
        endpoint = RecordingEndpoint(json.dumps({
            "action_type": "collect_block",
            "arguments": {"block": "oak_log", "count": 999},
            "completion_claim": False,
        }))
        factory = _factory(Path(td), endpoint)
        with pytest.raises(SemPaperModelPlannerError, match="action contract"):
            _decide(factory)
