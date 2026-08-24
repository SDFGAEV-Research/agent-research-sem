from __future__ import annotations

from typing import Protocol
from research_platform.platform.kernel import JsonInput

from .contracts import JsonHttpResponse, ModelEndpointRequest, ModelEndpointResponse, ModelEndpointRoute


class JsonHttpTransportPort(Protocol):
    """HTTP transport seam; retries and process lifecycle stay outside it."""

    def post_json(self, url: str, body: dict[str, JsonInput], *, timeout_s: float) -> JsonHttpResponse: ...


class ModelEndpointPort(Protocol):
    """Narrow synchronous inference seam over one exact model deployment."""

    def complete(self, request: ModelEndpointRequest) -> ModelEndpointResponse: ...


class ModelEndpointFactoryPort(Protocol):
    def create(self, route: ModelEndpointRoute) -> ModelEndpointPort: ...


__all__ = ["JsonHttpTransportPort", "ModelEndpointFactoryPort", "ModelEndpointPort"]
