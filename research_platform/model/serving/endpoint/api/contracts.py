from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

from research_platform.model.request.api import ModelRequestEnvelope
from research_platform.platform.kernel import canonical_digest, JsonInput, JsonValue


@dataclass(frozen=True, slots=True)
class ModelEndpointRequest:
    """One request sent to an already-bound, qualified model endpoint."""

    request: ModelRequestEnvelope
    deployment_id: str
    deployment_generation: str
    body: Mapping[str, JsonInput]

    def __post_init__(self) -> None:
        if not self.deployment_id.strip():
            raise ValueError("model endpoint deployment_id is required")
        if len(self.deployment_generation) != 64:
            raise ValueError("model endpoint deployment_generation must be SHA-256")
        if not isinstance(self.body, Mapping):
            raise TypeError("model endpoint request body must be a mapping")

    def digest(self) -> str:
        return canonical_digest({
            "request_envelope": self.request.envelope_digest,
            "deployment_id": self.deployment_id,
            "deployment_generation": self.deployment_generation,
            "body": dict(self.body),
        })


@dataclass(frozen=True, slots=True)
class ModelEndpointRoute:
    """Operational route bound to one qualified deployment identity."""

    deployment_id: str
    deployment_generation: str
    base_url: str
    completion_path: str = "/v1/chat/completions"
    timeout_s: float = 120.0

    def __post_init__(self) -> None:
        if not self.deployment_id.strip() or len(self.deployment_generation) != 64:
            raise ValueError("model endpoint route requires exact deployment identity")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("model endpoint route base_url must be an absolute HTTP(S) URL")
        if not self.completion_path.startswith("/"):
            raise ValueError("model endpoint completion_path must be absolute")
        if self.timeout_s <= 0:
            raise ValueError("model endpoint timeout_s must be positive")

    @property
    def completion_url(self) -> str:
        return self.base_url.rstrip("/") + self.completion_path


@dataclass(frozen=True, slots=True)
class JsonHttpResponse:
    status_code: int
    body: JsonValue

    def __post_init__(self) -> None:
        if self.status_code < 100:
            raise ValueError("HTTP status code is invalid")


@dataclass(frozen=True, slots=True)
class ModelEndpointResponse:
    """Transport result; scientific meaning is owned by the consuming project."""

    request_id: str
    deployment_id: str
    text: str
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    response_digest: str = ""

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.deployment_id.strip():
            raise ValueError("model endpoint response identity is required")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("model endpoint response text must be non-empty")
        for name in ("input_tokens", "output_tokens"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be non-negative")
        expected = canonical_digest({
            "request_id": self.request_id,
            "deployment_id": self.deployment_id,
            "text": self.text,
            "finish_reason": self.finish_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        })
        if self.response_digest and self.response_digest != expected:
            raise ValueError("model endpoint response digest mismatch")
        object.__setattr__(self, "response_digest", expected)


class ModelEndpointError(RuntimeError):
    """The endpoint could not produce a response satisfying its transport ABI."""


__all__ = [
    "JsonHttpResponse",
    "ModelEndpointError",
    "ModelEndpointRequest",
    "ModelEndpointResponse",
    "ModelEndpointRoute",
]
