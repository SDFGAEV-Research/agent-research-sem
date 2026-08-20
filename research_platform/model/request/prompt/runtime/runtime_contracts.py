from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActivePromptBundle:
    prompt_id: str
    role: str
    version: str
    digest: str
    text: str
    output_schema: str
    model_family: str
    temperature: float
    top_p: float
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class PromptResolution:
    generation_id: str
    bundle: ActivePromptBundle
