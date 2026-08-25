from __future__ import annotations
from dataclasses import dataclass

from research_platform.platform.kernel import JsonValue

@dataclass(frozen=True, slots=True)
class AggregateValue:
    aggregate_id: str
    version: int
    generation: str
    digest: str
    payload: JsonValue

@dataclass(frozen=True, slots=True)
class AtomicMutation:
    aggregate_id: str
    expected_version: int
    expected_generation: str
    new_generation: str
    new_digest: str
    new_payload: JsonValue

__all__=["AggregateValue","AtomicMutation"]
