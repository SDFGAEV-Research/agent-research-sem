from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from research_platform.model.serving.endpoint import (
    JsonHttpResponse,
    ModelEndpointError,
    ModelEndpointRequest,
    ModelEndpointRoute,
)
from research_platform.model.serving.endpoint.providers import OpenAICompatibleModelEndpoint
from research_platform.model.serving.runtime import ModelAdmissionController
from research_platform.platform.concurrency.api import ExecutionLaneKind
from research_platform.platform.concurrency.composition import build_concurrency_runtime


class Transport:
    def __init__(self, response: JsonHttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], float]] = []

    async def post_json(self, url: str, body: dict[str, object], *, timeout_s: float) -> JsonHttpResponse:
        self.calls.append((url, body, timeout_s))
        return self.response


def _request(*, deployment_id: str = "dep-1", generation: str = "a" * 64) -> ModelEndpointRequest:
    return ModelEndpointRequest(
        request=SimpleNamespace(request_id="rq-1", envelope_digest="e" * 64),
        deployment_id=deployment_id,
        deployment_generation=generation,
        body={"model": "qwen", "messages": []},
    )


@pytest.fixture
def endpoint_group():
    runtime = build_concurrency_runtime()
    group = runtime.open_task_group(f"test-model-endpoint:{uuid4().hex}")
    try:
        yield runtime, group
    finally:
        runtime.close()


def test_openai_compatible_endpoint_is_bound_to_exact_deployment_route(endpoint_group) -> None:
    runtime, group = endpoint_group
    transport = Transport(JsonHttpResponse(200, {
        "choices": [{"message": {"content": '{"action_type":"wait"}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }))
    route = ModelEndpointRoute("dep-1", "a" * 64, "http://127.0.0.1:30000")
    endpoint = OpenAICompatibleModelEndpoint(route=route, transport=transport, task_group=group, admission=ModelAdmissionController(1))

    result = endpoint.complete(_request())

    assert result.request_id == "rq-1"
    assert result.deployment_id == "dep-1"
    assert result.output_tokens == 4
    assert transport.calls == [("http://127.0.0.1:30000/v1/chat/completions", {"model": "qwen", "messages": []}, 120.0)]
    tasks = runtime.topology_snapshot().groups[0].tasks
    assert len(tasks) == 1
    assert tasks[0].lane_kind is ExecutionLaneKind.ASYNC_IO
    assert tasks[0].execution_done


def test_openai_compatible_endpoint_rejects_route_identity_drift_before_transport(endpoint_group) -> None:
    _runtime, group = endpoint_group
    transport = Transport(JsonHttpResponse(200, {"choices": [{"text": "ok"}]}))
    endpoint = OpenAICompatibleModelEndpoint(
        route=ModelEndpointRoute("dep-1", "a" * 64, "https://model.example"),
        transport=transport,
        task_group=group,
        admission=ModelAdmissionController(1),
    )
    with pytest.raises(ModelEndpointError, match="deployment"):
        endpoint.complete(_request(deployment_id="dep-2"))
    assert transport.calls == []


def test_openai_compatible_endpoint_rejects_ambiguous_response_shape(endpoint_group) -> None:
    _runtime, group = endpoint_group
    transport = Transport(JsonHttpResponse(200, {"choices": []}))
    endpoint = OpenAICompatibleModelEndpoint(
        route=ModelEndpointRoute("dep-1", "a" * 64, "https://model.example"),
        transport=transport,
        task_group=group,
        admission=ModelAdmissionController(1),
    )
    with pytest.raises(ModelEndpointError, match="exactly one choice"):
        endpoint.complete(_request())


def test_openai_compatible_endpoint_preserves_structured_http_error_detail(endpoint_group) -> None:
    _runtime, group = endpoint_group
    transport = Transport(JsonHttpResponse(400, {
        "message": "No user query found in messages.",
        "code": 400,
    }))
    endpoint = OpenAICompatibleModelEndpoint(
        route=ModelEndpointRoute("dep-1", "a" * 64, "https://model.example"),
        transport=transport,
        task_group=group,
        admission=ModelAdmissionController(1),
    )
    with pytest.raises(ModelEndpointError, match="No user query found in messages"):
        endpoint.complete(_request())
