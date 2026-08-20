from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from research_platform.data.record.api import ExecutionRecordPlane


class FactCriticality(StrEnum):
    REQUIRED = "required"
    IGNORABLE = "ignorable"


@dataclass(frozen=True, slots=True)
class DurableFact:
    fact_id: str
    fact_type: str
    schema_version: str
    criticality: FactCriticality
    payload: dict[str, object]
    artifact_refs: tuple[str, ...] = ()
    state_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.fact_id.strip() or not self.fact_type.strip() or not self.schema_version.strip():
            raise ValueError("durable fact identity fields must be non-empty")

    @property
    def record_plane(self) -> ExecutionRecordPlane:
        return ExecutionRecordPlane.DURABLE_FACT


class UnknownRequiredFact(RuntimeError):
    pass


@runtime_checkable
class DurableFactSinkPort(Protocol):
    def append(self, fact: DurableFact) -> None: ...


@runtime_checkable
class FactDecoderPort(Protocol):
    fact_type: str
    schema_version: str
    def decode(self, fact: DurableFact) -> object: ...


__all__ = ["DurableFact", "DurableFactSinkPort", "FactCriticality", "FactDecoderPort", "UnknownRequiredFact"]
