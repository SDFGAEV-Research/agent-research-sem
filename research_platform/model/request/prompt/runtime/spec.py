from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True, slots=True)
class PromptSection:
    section_id: str
    text: str
    priority: int


@dataclass(frozen=True, slots=True)
class PromptSpec:
    prompt_id: str
    role: str
    version: str
    model_family: str
    output_schema: str
    sections: tuple[PromptSection, ...]
    temperature: float
    top_p: float
    max_output_tokens: int

    def compile(self) -> str:
        return "\n\n".join(s.text.strip() for s in sorted(self.sections, key=lambda x: (x.priority, x.section_id))) + "\n"

    def bundle_digest(self) -> str:
        payload = {
            "prompt_id": self.prompt_id, "role": self.role, "version": self.version,
            "model_family": self.model_family, "output_schema": self.output_schema,
            "temperature": self.temperature, "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens,
            "text": self.compile(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
