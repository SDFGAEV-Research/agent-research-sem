from __future__ import annotations

"""Durable storage authority for one SEM session-state aggregate.

The session cell owns scientific mutation semantics.  This module owns only
the durable publication protocol: an append-first WAL, a checksummed primary
snapshot, a previous-good backup, revision/CAS identity, and recovery from the
latest valid durable candidate.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback keeps atomicity
    fcntl = None

from research_platform.platform.kernel import JsonObject, JsonValue, canonical_bytes
from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes

from projects.sem_paper.method.self_evolving_memory.evidence_api import EvidenceRecord, EvidenceSnapshot
from projects.sem_paper.method.self_evolving_memory.session_snapshot_contracts import (
    SEMSessionStateSnapshot,
    SessionLineageSnapshot,
    SessionMutationRecord,
)
from projects.sem_paper.method.self_evolving_memory.session_reducer import SEMSessionState


STATE_SCHEMA = "sem-session-state-durable.v2"
ENVELOPE_SCHEMA = "sem-session-state-envelope.v2"
DEFAULT_WAL_MAX_BYTES = 4 * 1024 * 1024


class DurableSEMSessionStateError(RuntimeError):
    """The durable state could not be safely read, recovered, or committed."""


def _document(snapshot: SEMSessionStateSnapshot) -> JsonObject:
    return {
        "schema": STATE_SCHEMA,
        "state": {
            "architecture_generation": snapshot.state.architecture_generation,
            "evidence_sequence": snapshot.state.evidence_sequence,
            "evolution_epoch": snapshot.state.evolution_epoch,
            "tasks_completed": snapshot.state.tasks_completed,
            "last_grounded_payload": snapshot.state.last_grounded_payload,
        },
        "evidence": {
            "sequence": snapshot.evidence.sequence,
            "digest": snapshot.evidence.digest,
            "rows": [
                {
                    "evidence_id": row.evidence_id,
                    "sequence": row.sequence,
                    "payload": row.payload,
                    "digest": row.digest,
                }
                for row in snapshot.evidence.rows
            ],
        },
        "lineage": {
            "revision": snapshot.lineage.revision,
            "mutation_tail": [
                {
                    "revision": row.revision,
                    "mutation_type": row.mutation_type,
                    "before_state_digest": row.before_state_digest,
                    "after_state_digest": row.after_state_digest,
                    "before_evidence_digest": row.before_evidence_digest,
                    "after_evidence_digest": row.after_evidence_digest,
                    "before_closed": row.before_closed,
                    "after_closed": row.after_closed,
                    "evidence_sequence": row.evidence_sequence,
                    "architecture_generation": row.architecture_generation,
                    "source_revision": row.source_revision,
                    "run_id": row.run_id,
                    "task_id": row.task_id,
                    "decision_cycle_id": row.decision_cycle_id,
                    "operation_id": row.operation_id,
                    "trace_id": row.trace_id,
                    "span_id": row.span_id,
                }
                for row in snapshot.lineage.mutation_tail
            ],
        },
    }


def _decode(document: JsonObject) -> SEMSessionStateSnapshot:
    if document.get("schema") != STATE_SCHEMA:
        raise DurableSEMSessionStateError("unsupported SEM durable state schema")
    state = document.get("state")
    evidence = document.get("evidence")
    lineage = document.get("lineage")
    if not isinstance(state, dict) or not isinstance(evidence, dict) or not isinstance(lineage, dict):
        raise DurableSEMSessionStateError("SEM durable state sections are invalid")
    rows = evidence.get("rows", ())
    mutation_tail = lineage.get("mutation_tail", ())
    if not isinstance(rows, (list, tuple)) or not isinstance(mutation_tail, (list, tuple)):
        raise DurableSEMSessionStateError("SEM durable state collections are invalid")
    snapshot_evidence = EvidenceSnapshot(
        int(evidence["sequence"]),
        tuple(
            EvidenceRecord(
                str(row["evidence_id"]),
                int(row["sequence"]),
                row["payload"],
                str(row["digest"]),
            )
            for row in rows
            if isinstance(row, dict)
        ),
        str(evidence["digest"]),
    )
    if len(snapshot_evidence.rows) != len(rows):
        raise DurableSEMSessionStateError("SEM durable evidence row is invalid")
    if tuple(row.sequence for row in snapshot_evidence.rows) != tuple(range(1, len(rows) + 1)):
        raise DurableSEMSessionStateError("SEM durable evidence sequence is not contiguous")
    snapshot_lineage = SessionLineageSnapshot(
        int(lineage["revision"]),
        tuple(
            SessionMutationRecord(
                revision=int(row["revision"]),
                mutation_type=str(row["mutation_type"]),
                before_state_digest=str(row["before_state_digest"]),
                after_state_digest=str(row["after_state_digest"]),
                before_evidence_digest=str(row["before_evidence_digest"]),
                after_evidence_digest=str(row["after_evidence_digest"]),
                before_closed=bool(row["before_closed"]),
                after_closed=bool(row["after_closed"]),
                evidence_sequence=int(row["evidence_sequence"]),
                architecture_generation=str(row["architecture_generation"]),
                source_revision=row.get("source_revision"),
                run_id=row.get("run_id"),
                task_id=row.get("task_id"),
                decision_cycle_id=row.get("decision_cycle_id"),
                operation_id=row.get("operation_id"),
                trace_id=row.get("trace_id"),
                span_id=row.get("span_id"),
            )
            for row in mutation_tail
            if isinstance(row, dict)
        ),
    )
    if len(snapshot_lineage.mutation_tail) != len(mutation_tail):
        raise DurableSEMSessionStateError("SEM durable lineage row is invalid")
    revisions = tuple(row.revision for row in snapshot_lineage.mutation_tail)
    if revisions != tuple(sorted(revisions)) or len(revisions) != len(set(revisions)):
        raise DurableSEMSessionStateError("SEM durable lineage revisions are not ordered")
    snapshot = SEMSessionStateSnapshot(
        SEMSessionState(
            architecture_generation=str(state["architecture_generation"]),
            evidence_sequence=int(state["evidence_sequence"]),
            evolution_epoch=int(state["evolution_epoch"]),
            tasks_completed=int(state["tasks_completed"]),
            last_grounded_payload=str(state["last_grounded_payload"]),
        ),
        snapshot_evidence,
        snapshot_lineage,
    )
    if snapshot.state.evidence_sequence != snapshot.evidence.sequence:
        raise DurableSEMSessionStateError("SEM state/evidence sequence mismatch")
    return snapshot


def _envelope(snapshot: SEMSessionStateSnapshot, revision: int) -> tuple[JsonObject, bytes, str]:
    payload = canonical_bytes(_document(snapshot))
    sha256 = hashlib.sha256(payload).hexdigest()
    value: JsonObject = {
        "schema": ENVELOPE_SCHEMA,
        "revision": revision,
        "payload": json.loads(payload.decode("utf-8")),
        "sha256": sha256,
    }
    return value, canonical_bytes(value), sha256


def _decode_envelope(value: object, *, source: Path) -> tuple[int, str, SEMSessionStateSnapshot, JsonObject]:
    if not isinstance(value, dict) or value.get("schema") != ENVELOPE_SCHEMA:
        raise DurableSEMSessionStateError(f"invalid SEM durable envelope: {source}")
    try:
        revision = int(value["revision"])
        payload = value["payload"]
        sha256 = str(value["sha256"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DurableSEMSessionStateError(f"invalid SEM durable envelope fields: {source}") from exc
    if revision < 0 or not isinstance(payload, dict) or len(sha256) != 64:
        raise DurableSEMSessionStateError(f"invalid SEM durable envelope identity: {source}")
    raw_payload = canonical_bytes(payload)
    if hashlib.sha256(raw_payload).hexdigest() != sha256:
        raise DurableSEMSessionStateError(f"SEM durable envelope checksum mismatch: {source}")
    return revision, sha256, _decode(payload), value


class FileSEMSessionStateStore:
    """Single-session durable store with WAL, backup recovery, and CAS."""

    def __init__(self, path: Path, *, wal_max_bytes: int = DEFAULT_WAL_MAX_BYTES) -> None:
        if wal_max_bytes <= 0:
            raise ValueError("SEM durable WAL max_bytes must be positive")
        self.path = path
        self.wal_path = path.with_name(path.name + ".wal")
        self.backup_path = path.with_name(path.name + ".bak")
        self.lock_path = path.with_name(path.name + ".lock")
        self.wal_max_bytes = wal_max_bytes
        self._observed_sha256: str | None = None
        self._observed_revision: int | None = None

    @contextmanager
    def _lock_file(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_json(self, path: Path) -> object:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DurableSEMSessionStateError(f"SEM durable JSON cannot be read: {path}") from exc

    def _read_wal(self) -> list[tuple[int, str, SEMSessionStateSnapshot, JsonObject]]:
        if not self.wal_path.is_file():
            return []
        candidates: list[tuple[int, str, SEMSessionStateSnapshot, JsonObject]] = []
        try:
            lines = self.wal_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except (OSError, UnicodeError) as exc:
            raise DurableSEMSessionStateError("SEM durable WAL cannot be read") from exc
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            if not line.endswith("\n"):
                continue
            try:
                candidates.append(_decode_envelope(json.loads(line), source=self.wal_path))
            except (json.JSONDecodeError, DurableSEMSessionStateError) as exc:
                raise DurableSEMSessionStateError(
                    f"SEM durable WAL corrupt complete record at line {index}"
                ) from exc
        return candidates

    def _candidates(self) -> list[tuple[int, str, SEMSessionStateSnapshot, JsonObject]]:
        candidates: list[tuple[int, str, SEMSessionStateSnapshot, JsonObject]] = []
        recoverable_errors: list[DurableSEMSessionStateError] = []
        for path in (self.path, self.backup_path):
            if path.is_file():
                try:
                    candidates.append(_decode_envelope(self._read_json(path), source=path))
                except DurableSEMSessionStateError as exc:
                    # A torn primary/backup is recoverable when another durable
                    # candidate exists. WAL corruption remains fail-closed in
                    # _read_wal because it is the commit journal.
                    recoverable_errors.append(exc)
        candidates.extend(self._read_wal())
        if not candidates and recoverable_errors:
            raise recoverable_errors[0]
        return candidates

    def _latest(self) -> tuple[int, str, SEMSessionStateSnapshot, JsonObject] | None:
        candidates = self._candidates()
        if not candidates:
            return None
        highest_revision = max(row[0] for row in candidates)
        highest = [row for row in candidates if row[0] == highest_revision]
        if len({row[1] for row in highest}) != 1:
            raise DurableSEMSessionStateError("SEM durable candidates disagree at one revision")
        return highest[-1]

    def exists(self) -> bool:
        with self._lock_file():
            return any(path.is_file() for path in (self.path, self.backup_path, self.wal_path))

    def write(self, snapshot: SEMSessionStateSnapshot) -> None:
        with self._lock_file():
            current = self._latest()
            if current is not None:
                if self._observed_sha256 is None:
                    raise DurableSEMSessionStateError(
                        "SEM durable state requires read-before-write for an existing session"
                    )
                if current[1] != self._observed_sha256:
                    raise DurableSEMSessionStateError(
                        "SEM durable state concurrent update detected; restore and retry"
                    )
                revision = current[0] + 1
                atomic_replace_bytes(self.backup_path, canonical_bytes(current[3]))
            else:
                revision = 1
            value, encoded, sha256 = _envelope(snapshot, revision)
            if self.wal_path.is_file() and self.wal_path.stat().st_size + len(encoded) + 1 > self.wal_max_bytes:
                atomic_replace_bytes(self.wal_path, encoded + b"\n")
            else:
                with self.wal_path.open("ab") as handle:
                    handle.write(encoded + b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            atomic_replace_bytes(self.path, encoded)
            self._observed_sha256 = sha256
            self._observed_revision = revision

    def read(self) -> SEMSessionStateSnapshot:
        with self._lock_file():
            current = self._latest()
            if current is None:
                raise DurableSEMSessionStateError("SEM durable state does not exist")
            self._observed_sha256 = current[1]
            self._observed_revision = current[0]
            return current[2]

    def repair_primary(self) -> SEMSessionStateSnapshot:
        """Restore the primary snapshot from the latest valid WAL/backup candidate."""

        with self._lock_file():
            current = self._latest()
            if current is None:
                raise DurableSEMSessionStateError("SEM durable state has no recoverable candidate")
            atomic_replace_bytes(self.path, canonical_bytes(current[3]))
            self._observed_sha256 = current[1]
            self._observed_revision = current[0]
            return current[2]


__all__ = ["DurableSEMSessionStateError", "FileSEMSessionStateStore"]
