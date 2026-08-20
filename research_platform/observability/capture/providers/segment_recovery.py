from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ..api.contracts import RawObservationCorruptionError, RawObservationReceipt


@dataclass(frozen=True, slots=True)
class RecoveredRawSegment:
    sequence: int
    idempotency: dict[str,RawObservationReceipt]


def recover_raw_segment(
    target:Path,
    *,
    family:str,
    schema_version:str,
    run_id:str,
)->RecoveredRawSegment:
    sequence=0
    idempotency:dict[str,RawObservationReceipt]={}
    if not target.exists():
        return RecoveredRawSegment(sequence,idempotency)
    for line_no,line in enumerate(target.read_text(encoding="utf-8").splitlines(),1):
        try:
            row=json.loads(line)
        except json.JSONDecodeError as exc:
            raise RawObservationCorruptionError(f"{target}: line {line_no}: invalid json") from exc
        seq=int(row.get("sequence",0))
        if seq!=sequence+1:
            raise RawObservationCorruptionError(f"{target}: line {line_no}: non-contiguous sequence")
        if str(row.get("schema_version"))!=schema_version:
            raise RawObservationCorruptionError(
                f"{target}: line {line_no}: schema drift {row.get('schema_version')} != {schema_version}"
            )
        sequence=seq
        idem=row.get("idempotency_key")
        if idem:
            key=str(idem)
            if key in idempotency:
                raise RawObservationCorruptionError(f"{target}: duplicate idempotency key {key}")
            idempotency[key]=RawObservationReceipt(
                family,schema_version,run_id,str(target),seq,
                str(row["record_sha256"]),len((line+"\n").encode("utf-8")),
            )
    return RecoveredRawSegment(sequence,idempotency)
