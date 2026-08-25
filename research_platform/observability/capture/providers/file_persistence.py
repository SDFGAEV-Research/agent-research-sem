from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from typing import Mapping

from research_platform.platform.kernel import ExecutionContext, JsonObject
from research_platform.platform.kernel.errors import describe_exception

from ..api.contracts import RawObservationReceipt, RawObservationSchema
from .segment_pool import RawSegmentPool


class FileRawObservationPersistence:
    """Filesystem-backed raw observation persistence authority."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._pool = RawSegmentPool(root)

    @staticmethod
    def _encode_record(record: dict[str, object]) -> tuple[bytes, str]:
        canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        encoded = (
            json.dumps(
                {**record, "record_sha256": digest},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        return encoded, digest

    def append(
        self,
        context: ExecutionContext,
        schema: RawObservationSchema,
        payload: JsonObject,
        *,
        timestamp: float | None,
        idempotency_key: str | None,
    ) -> RawObservationReceipt:
        segment = self._pool.get(context.run_id, schema.family, schema.schema_version)
        with segment.lock:
            if idempotency_key is not None:
                previous = segment.previous(idempotency_key)
                if previous is not None:
                    return previous
            sequence = segment.sequence + 1
            record: dict[str, object] = {
                "sequence": sequence,
                "timestamp": time.time() if timestamp is None else float(timestamp),
                "family": schema.family,
                "schema_version": schema.schema_version,
                "retention": schema.retention.value,
                "context": asdict(context),
                "payload": dict(payload),
            }
            if idempotency_key is not None:
                record["idempotency_key"] = idempotency_key
            encoded, digest = self._encode_record(record)
            receipt = RawObservationReceipt(
                schema.family,
                schema.schema_version,
                context.run_id,
                str(segment.target),
                sequence,
                digest,
                len(encoded),
            )
            segment.append(encoded, receipt, idempotency_key)
            return receipt

    def verify(self, run_id: str, family: str) -> tuple[str, ...]:
        target = RawSegmentPool.target(self.root, run_id, family)
        lock = self._pool.lock_for(run_id, family)
        with lock:
            if not target.exists():
                return (f"missing segment: {target}",)
            errors: list[str] = []
            expected = 1
            seen_ids: set[object] = set()
            for line_no, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"line {line_no}: invalid json: {describe_exception(exc).safe_message}")
                    continue
                digest = row.pop("record_sha256", None)
                canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if digest != actual:
                    errors.append(f"line {line_no}: digest mismatch")
                if row.get("sequence") != expected:
                    errors.append(f"line {line_no}: expected sequence {expected}, got {row.get('sequence')}")
                idem = row.get("idempotency_key")
                if idem and idem in seen_ids:
                    errors.append(f"line {line_no}: duplicate idempotency key {idem}")
                if idem:
                    seen_ids.add(idem)
                expected += 1
            return tuple(errors)

    def close(self) -> None:
        self._pool.close()


__all__ = ["FileRawObservationPersistence"]
