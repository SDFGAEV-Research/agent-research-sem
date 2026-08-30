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
    def __init__(self, text: str, finish_reason: str | None = "stop") -> None:
        self.text = text
        self.finish_reason = finish_reason
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return ModelEndpointResponse(
            request_id=request.request.request_id,
            deployment_id=request.deployment_id,
            text=self.text,
            finish_reason=self.finish_reason,
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
        response_format = request.body["response_format"]
        assert response_format["type"] == "json_schema"
        spec = response_format["json_schema"]
        assert spec["name"] == "planner_action_v2"
        assert spec["strict"] is True
        schema = spec["schema"]
        assert schema["additionalProperties"] is False
        assert schema["required"] == ["action_type", "arguments", "completion_claim"]


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


def test_model_planner_rejects_non_terminal_finish_reason_even_for_valid_json() -> None:
    payload = json.dumps({
        "action_type": "collect_block",
        "arguments": {"block": "oak_log", "count": 1},
        "completion_claim": False,
    })
    for finish_reason in (None, "length", "content_filter", "tool_calls"):
        with tempfile.TemporaryDirectory() as td:
            endpoint = RecordingEndpoint(payload, finish_reason=finish_reason)
            factory = _factory(Path(td), endpoint)
            with pytest.raises(SemPaperModelPlannerError, match="did not complete normally") as captured:
                _decide(factory)
            assert captured.value.phase == "response_completion"


def test_model_planner_projects_unbounded_minecraft_diagnostics_before_prompt_binding() -> None:
    with tempfile.TemporaryDirectory() as td:
        endpoint = RecordingEndpoint(json.dumps({
            "action_type": "collect_block",
            "arguments": {"block": "cobblestone", "count": 1},
            "completion_claim": False,
        }))
        factory = _factory(Path(td), endpoint)
        planner = factory.create(
            role=BranchRole.CONTROL,
            candidate=None,
            task=MinecraftTaskSpec("task-nav", "navigation", "return to spawn"),
            method=object(),
        )
        protocol_packets = [
            {
                "packet": "entity_metadata",
                "sequence": index,
                "entity_id": 573,
                "metadata_types": ["int"],
            }
            for index in range(177)
        ]
        def pickup_error(packet_count: int):
            return {
                "phase": "pickup",
                "message": "ITEM_DROP_NOT_OBSERVED",
                "expected_item": "stone",
                "position": {"x": 3.0, "y": 64.0, "z": 1.0},
                "association_radius": 0.5,
                "drop_candidates": [],
                "spawn_candidates": [],
                "collection_candidates": [],
                "protocol_packets": protocol_packets[:packet_count],
            }

        state = {
            "username": "SEM_bot",
            "position": {"x": 1.0, "y": 64.0, "z": 2.0},
            "health": 20.0,
            "food": 20.0,
            "dimension": "overworld",
            "inventory": {"oak_log": 4, "cobblestone": 3},
            "nearby_entities": [],
            "anchors": {"spawn": {"x": 0.0, "y": 64.0, "z": 0.0}},
            "deaths": 0,
            "last_action_verified": False,
            "last_action": {"action_type": "collect_block", "block": "stone"},
            "last_outcome": {
                "status": "partial",
                "code": "COLLECTION_INCOMPLETE",
                "requested_count": 3,
                "collected_count": 0,
                "errors": [
                    pickup_error(48),
                    pickup_error(48),
                    pickup_error(177),
                ],
            },
            "last_event_sequence": 42,
        }
        raw_state_text = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        assert len(raw_state_text) > 24_000

        decision = planner.decide(
            task=MinecraftTaskSpec("task-nav", "navigation", "return to spawn"),
            context=ExecutionContext("run-1", "trace-1", "span-1", branch_id="control", decision_cycle_id="cycle-nav"),
            state=state,
            memory_context="",
            step=0,
            prior_actions=(),
        )
        assert decision.action_type == "collect_block"
        prompt = endpoint.requests[0].body["messages"][0]["content"]
        assert "sem-paper.minecraft-planner-state.v1" in prompt
        assert '"protocol_packet_count":177' in prompt
        assert '"protocol_packets"' not in prompt
        assert '"packet":"entity_metadata"' not in prompt
        assert '"inventory":{"cobblestone":3,"oak_log":4}' in prompt
