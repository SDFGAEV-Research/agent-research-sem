from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AggregateValue:
    aggregate_id: str
    version: int
    generation: str
    digest: str
    payload: object

@dataclass(frozen=True, slots=True)
class AtomicMutation:
    aggregate_id: str
    expected_version: int
    expected_generation: str
    new_generation: str
    new_digest: str
    new_payload: object

__all__=["AggregateValue","AtomicMutation"]
