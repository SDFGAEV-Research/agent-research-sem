from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RetentionClass(StrEnum):
    HOT_DEBUG = "hot_debug"
    RUN_DURABLE = "run_durable"
    SCIENTIFIC_DURABLE = "scientific_durable"


@dataclass(frozen=True, slots=True)
class RawObservationSchema:
    family: str
    schema_version: str
    required_fields: tuple[str, ...]
    retention: RetentionClass
    description: str


@dataclass(frozen=True, slots=True)
class RawObservationReceipt:
    family: str
    schema_version: str
    run_id: str
    segment_path: str
    sequence: int
    payload_sha256: str
    bytes_written: int


class RawObservationCorruptionError(RuntimeError):
    pass
