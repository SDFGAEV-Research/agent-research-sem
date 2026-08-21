from __future__ import annotations

from types import SimpleNamespace

import pytest

from research_platform.model.serving.endpoint import (
    JsonHttpResponse,
    ModelEndpointError,
    ModelEndpointRequest,
    ModelEndpointRoute,
)
from research_platform.model.serving.endpoint.providers import OpenAICompatibleModelEndpoint


class Transport:
    def __init__(self, response: JsonHttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], float]] = []

    def post_json(self, url: str, body: dict[str, object], *, timeout_s: float) -> JsonHttpResponse:
        self.calls.append((url, body, timeout_s))
        return self.response


def _request(*, deployment_id: str = "dep-1", generation: str = "a" * 64) -> ModelEndpointRequest:
    return ModelEndpointRequest(
        request=SimpleNamespace(request_id="rq-1", envelope_digest="e" * 64),
        deployment_id=deployment_id,
        deployment_generation=generation,
        body={"model": "qwen", "messages": []},
    )


def test_openai_compatible_endpoint_is_bound_to_exact_deployment_route() -> None:
    transport = Transport(JsonHttpResponse(200, {
        "choices": [{"message": {"content": '{"action_type":"wait"}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }))
    route = ModelEndpointRoute("dep-1", "a" * 64, "http://127.0.0.1:30000")
    endpoint = OpenAICompatibleModelEndpoint(route=route, transport=transport)

    result = endpoint.complete(_request())

    assert result.request_id == "rq-1"
    assert result.deployment_id == "dep-1"
    assert result.output_tokens == 4
    assert transport.calls == [("http://127.0.0.1:30000/v1/chat/completions", {"model": "qwen", "messages": []}, 120.0)]


def test_openai_compatible_endpoint_rejects_route_identity_drift_before_transport() -> None:
    transport = Transport(JsonHttpResponse(200, {"choices": [{"text": "ok"}]}))
    endpoint = OpenAICompatibleModelEndpoint(
        route=ModelEndpointRoute("dep-1", "a" * 64, "https://model.example"),
        transport=transport,
    )
    with pytest.raises(ModelEndpointError, match="deployment"):
        endpoint.complete(_request(deployment_id="dep-2"))
    assert transport.calls == []


def test_openai_compatible_endpoint_rejects_ambiguous_response_shape() -> None:
    transport = Transport(JsonHttpResponse(200, {"choices": []}))
    endpoint = OpenAICompatibleModelEndpoint(
        route=ModelEndpointRoute("dep-1", "a" * 64, "https://model.example"),
        transport=transport,
    )
    with pytest.raises(ModelEndpointError, match="exactly one choice"):
        endpoint.complete(_request())
