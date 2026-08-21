from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from research_platform.model.request.api import ModelRequestEnvelope
from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity


@dataclass(frozen=True, slots=True)
class PromptDynamicBlock:
    """Project-owned dynamic evidence expressed in the prompt API vocabulary."""

    kind: str
    content: str
    source_digest: str
    sequence: int


@dataclass(frozen=True, slots=True)
class PromptBodyContext:
    """Compiled prompt facts exposed to a project body-shaping function."""

    prompt_id: str
    prompt_digest: str
    role: str
    model_id: str
    output_schema: str
    compiled_text: str
    temperature: float
    top_p: float
    max_output_tokens: int


PromptRequestBodyBuilder = Callable[[PromptBodyContext], Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class PromptBoundRequest:
    request: ModelRequestEnvelope
    body: dict[str, object]
    prompt_generation_id: str
    prompt_id: str
    prompt_digest: str


class PromptRequestBindingPort(Protocol):
    """Frozen prompt-to-model-request port consumed by project composition."""

    def build(
        self,
        *,
        blocks: tuple[PromptDynamicBlock, ...],
        context_length: int,
        request_id: str,
        context: ExecutionContext,
        model: ImmutableModelIdentity,
        body_builder: PromptRequestBodyBuilder,
        source_artifact_refs: tuple[str, ...] = (),
        source_state_refs: tuple[str, ...] = (),
    ) -> PromptBoundRequest: ...


__all__ = [
    "PromptBoundRequest",
    "PromptBodyContext",
    "PromptDynamicBlock",
    "PromptRequestBindingPort",
    "PromptRequestBodyBuilder",
]
