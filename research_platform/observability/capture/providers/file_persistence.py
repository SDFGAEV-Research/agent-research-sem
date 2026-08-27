from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from threading import Lock
import time

from research_platform.platform.concurrency.api import Deadline, SerialActorPort, TaskGroupPort
from research_platform.platform.kernel import ExecutionContext, JsonObject
from research_platform.platform.kernel.errors import describe_exception

from ..api.contracts import RawObservationReceipt, RawObservationSchema
from .segment_pool import RawSegmentPool


class FileRawObservationPersistence:
    """Filesystem-backed raw observation persistence with actor-owned writers."""

    def __init__(self, root: Path, *, task_group: TaskGroupPort) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._pool = RawSegmentPool(root)
        self._task_group = task_group
        self._actors_lock = Lock()
        self._actors: dict[tuple[str, str], SerialActorPort] = {}
        self._closed = False

    @staticmethod
    def _actor_suffix(run_id: str, family: str) -> str:
        return hashlib.sha256(f"{run_id}\x00{family}".encode("utf-8")).hexdigest()

    def _actor_for(self, run_id: str, family: str) -> SerialActorPort:
        key = (run_id, family)
        with self._actors_lock:
            if self._closed:
                raise RuntimeError("raw observation persistence is closed")
            actor = self._actors.get(key)
            if actor is None:
                suffix = self._actor_suffix(run_id, family)
                actor = self._task_group.open_serial_actor(
                    f"raw-segment:{suffix}",
                    lane_id=f"raw-segment:{suffix}",
                )
                self._actors[key] = actor
            return actor

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
        actor = self._actor_for(context.run_id, schema.family)

        def append_owned() -> RawObservationReceipt:
            segment = self._pool.get(context.run_id, schema.family, schema.schema_version)
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

        return actor.call("append", append_owned)

    def verify(self, run_id: str, family: str) -> tuple[str, ...]:
        target = RawSegmentPool.target(self.root, run_id, family)
        actor = self._actor_for(run_id, family)

        def freeze_prefix_owned() -> int | None:
            if not target.exists():
                return None
            return target.stat().st_size

        snapshot_size = actor.call("freeze-verify-prefix", freeze_prefix_owned)
        if snapshot_size is None:
            return (f"missing segment: {target}",)
        errors: list[str] = []
        expected = 1
        seen_ids: set[object] = set()
        with target.open("rb") as handle:
            remaining = snapshot_size
            line_no = 0
            while remaining > 0:
                raw = handle.readline(remaining)
                if not raw:
                    break
                remaining -= len(raw)
                line_no += 1
                try:
                    line = raw.decode("utf-8")
                    row = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(
                        f"line {line_no}: invalid json: {describe_exception(exc).safe_message}"
                    )
                    continue
                digest = row.pop("record_sha256", None)
                canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if digest != actual:
                    errors.append(f"line {line_no}: digest mismatch")
                if row.get("sequence") != expected:
                    errors.append(
                        f"line {line_no}: expected sequence {expected}, got {row.get('sequence')}"
                    )
                idem = row.get("idempotency_key")
                if idem and idem in seen_ids:
                    errors.append(f"line {line_no}: duplicate idempotency key {idem}")
                if idem:
                    seen_ids.add(idem)
                expected += 1
        return tuple(errors)

    def close(self) -> None:
        """Seal every opened segment and join its actor-owned close operation.

        Algorithm-Complexity: O(N)
        Algorithm-Rationale: Each opened raw segment is closed exactly once through its actor-owned lane; the pass is linear in the number of opened segments and uses one shared shutdown deadline without accumulating an unbounded handle fanout.
        """

        with self._actors_lock:
            if self._closed:
                return
            self._closed = True
            actors = dict(self._actors)
        writers = self._pool.seal()
        errors: list[BaseException] = []
        deadline = Deadline.after(30.0)
        for key, writer in writers:
            actor = actors.get(key)
            if actor is None:
                errors.append(RuntimeError(f"raw segment writer has no actor owner: {key}"))
                continue
            try:
                actor.call("close-writer", writer.close, deadline=deadline)
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise ExceptionGroup("raw observation persistence close failed", errors)
