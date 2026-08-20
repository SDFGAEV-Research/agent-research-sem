from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import time

from research_platform.platform.kernel import canonical_bytes

from .runtime_history_contracts import (
    RUNTIME_HISTORY_ROW_SCHEMA_VERSION,
    RuntimeHistoryEntry,
    RuntimeHistoryProjectionKind,
)


def runtime_state_dict(state: object) -> dict[str, object]:
    return asdict(state)


def runtime_state_digest(state: dict[str, object]) -> str:
    return hashlib.sha256(canonical_bytes(state)).hexdigest()


def build_runtime_history_row(
    *,
    sequence: int,
    state: object,
    projection_kind: RuntimeHistoryProjectionKind,
    previous_sha256: str | None,
) -> tuple[dict[str, object], RuntimeHistoryEntry]:
    state_dict = runtime_state_dict(state)
    state_sha256 = runtime_state_digest(state_dict)
    timestamp = time.time()
    base: dict[str, object] = {
        "schema_version": RUNTIME_HISTORY_ROW_SCHEMA_VERSION,
        "sequence": sequence,
        "timestamp": timestamp,
        "state": state_dict,
        "state_sha256": state_sha256,
        "projection_kind": projection_kind.value,
        "previous_sha256": previous_sha256,
    }
    row_sha256 = hashlib.sha256(canonical_bytes(base)).hexdigest()
    row = {**base, "row_sha256": row_sha256}
    entry = RuntimeHistoryEntry(
        sequence=sequence,
        timestamp=timestamp,
        state=state_dict,
        state_sha256=state_sha256,
        projection_kind=projection_kind,
        previous_sha256=previous_sha256,
        row_sha256=row_sha256,
    )
    return row, entry


def encode_runtime_history_row(row: dict[str, object]) -> bytes:
    return json.dumps(
        row,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"


__all__ = [
    "build_runtime_history_row",
    "encode_runtime_history_row",
    "runtime_state_dict",
    "runtime_state_digest",
]
