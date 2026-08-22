from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from research_platform.model.serving.endpoint.api import (
    JsonHttpResponse,
    JsonHttpTransportPort,
    ModelEndpointError,
    ModelEndpointPort,
    ModelEndpointRequest,
    ModelEndpointResponse,
    ModelEndpointRoute,
)
from research_platform.platform.kernel import canonical_digest


def _error_detail(body: object) -> str:
    if isinstance(body, Mapping):
        for key in ("message", "detail", "error"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:512]
    return f"response_body_digest={canonical_digest(body)}"


class UrllibJsonTransport(JsonHttpTransportPort):
    """Dependency-free JSON transport for a host-composed endpoint route."""

    def __init__(self, *, headers: tuple[tuple[str, str], ...] = ()) -> None:
        self._headers = (('Content-Type', 'application/json'), *headers)

    def post_json(self, url: str, body: dict[str, object], *, timeout_s: float) -> JsonHttpResponse:
        request = Request(
            url,
            data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers=dict(self._headers),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_s) as response:
                raw = response.read()
                parsed = json.loads(raw.decode("utf-8"))
                return JsonHttpResponse(int(response.status), parsed)
        except HTTPError as exc:
            try:
                raw = exc.read()
                parsed = json.loads(raw.decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                parsed = {"message": "HTTP error response body unavailable"}
            return JsonHttpResponse(int(exc.code), parsed)
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ModelEndpointError(f"model endpoint HTTP transport failed: {type(exc).__name__}") from exc


class OpenAICompatibleModelEndpoint(ModelEndpointPort):
    """Strict OpenAI-compatible response adapter for SGLang/vLLM-style APIs."""

    def __init__(self, *, route: ModelEndpointRoute, transport: JsonHttpTransportPort) -> None:
        self.route = route
        self.transport = transport

    def complete(self, request: ModelEndpointRequest) -> ModelEndpointResponse:
        if request.deployment_id != self.route.deployment_id:
            raise ModelEndpointError("endpoint request deployment does not match route")
        if request.deployment_generation != self.route.deployment_generation:
            raise ModelEndpointError("endpoint request deployment generation does not match route")
        response = self.transport.post_json(
            self.route.completion_url,
            dict(request.body),
            timeout_s=self.route.timeout_s,
        )
        if not 200 <= response.status_code < 300:
            raise ModelEndpointError(
                f"model endpoint returned HTTP {response.status_code}: {_error_detail(response.body)}"
            )
        if not isinstance(response.body, Mapping):
            raise ModelEndpointError("model endpoint response body must be an object")
        choices = response.body.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
            raise ModelEndpointError("model endpoint response must contain exactly one choice")
        choice = choices[0]
        message = choice.get("message")
        text = message.get("content") if isinstance(message, Mapping) else choice.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ModelEndpointError("model endpoint choice has no text content")
        usage = response.body.get("usage")
        input_tokens = usage.get("prompt_tokens") if isinstance(usage, Mapping) else None
        output_tokens = usage.get("completion_tokens") if isinstance(usage, Mapping) else None
        if input_tokens is not None and not isinstance(input_tokens, int):
            raise ModelEndpointError("model endpoint prompt_tokens must be an integer")
        if output_tokens is not None and not isinstance(output_tokens, int):
            raise ModelEndpointError("model endpoint completion_tokens must be an integer")
        finish_reason = choice.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise ModelEndpointError("model endpoint finish_reason must be text")
        return ModelEndpointResponse(
            request_id=request.request.request_id,
            deployment_id=request.deployment_id,
            text=text,
            finish_reason=finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


__all__ = ["OpenAICompatibleModelEndpoint", "UrllibJsonTransport"]
