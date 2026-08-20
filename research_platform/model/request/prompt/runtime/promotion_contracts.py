from __future__ import annotations

from dataclasses import dataclass

from research_platform.platform.kernel import canonical_digest

from .publication_common import sha256_bytes
from .qualification import PromptQualification


@dataclass(frozen=True, slots=True)
class PromptPromotionEvidence:
    generation_id:str
    generation_payload_sha256:str
    canary_suite_digest:str
    qualifications:tuple[PromptQualification,...]
    model_resume_key:tuple[object,...]
    objective_evidence_digest:str
    created_at:float

    def digest(self)->str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class PromptPromotionRecord:
    generation_id:str
    generation_payload_sha256:str
    promotion_evidence_digest:str
    previous_generation_id:str|None
    activated_at:float
