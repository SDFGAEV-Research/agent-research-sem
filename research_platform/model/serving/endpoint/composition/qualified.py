from __future__ import annotations

from research_platform.model.serving.endpoint.api import (
    ModelEndpointPort,
    ModelEndpointRoute,
    QualifiedModelEndpointBinding,
)
from research_platform.platform.concurrency.api import TaskGroupPort
from research_platform.model.serving.endpoint.providers import (
    OpenAICompatibleModelEndpoint,
    AsyncioJsonTransport,
)


def build_openai_compatible_qualified_endpoint(
    binding: QualifiedModelEndpointBinding,
    *,
    api_key: str = "",
    timeout_s: float | None = None,
    task_group: TaskGroupPort,
) -> ModelEndpointPort:
    """Materialize one endpoint from a platform-qualified binding."""

    headers: tuple[tuple[str, str], ...] = ()
    if api_key:
        headers = (("Authorization", f"Bearer {api_key}"),)
    return OpenAICompatibleModelEndpoint(
        route=ModelEndpointRoute(
            deployment_id=binding.deployment_id,
            deployment_generation=binding.deployment_generation,
            base_url=binding.base_url,
            completion_path=binding.completion_path,
            timeout_s=timeout_s or binding.timeout_s,
        ),
        transport=AsyncioJsonTransport(headers=headers),
        task_group=task_group,
    )


__all__ = ["build_openai_compatible_qualified_endpoint"]
