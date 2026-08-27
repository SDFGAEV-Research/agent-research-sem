from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
from contextlib import AbstractContextManager

from research_platform.platform.kernel.durability.file_lock import InterprocessFileLock
from research_platform.platform.kernel.durability.file_lock import InterprocessLockBusy
from research_platform.platform.concurrency.api import SerialActorPort
from research_platform.runtime.server.api import (
    ServerOperationEffect,
    ServerOperationFinished,
    ServerOperationJournalPort,
    ServerOperationStarted,
    ServerOperationKind,
    ServerOperationRecord,
    ServerOperationResolved,
    ServerOperationResolution,
    ServerOperationState,
    ServerMutationBusy,
    ServerTransportBusy,
)


class ServerOperationJournalIntegrityError(RuntimeError):
    """The durable server-operation ledger cannot be safely replayed."""


class _NonBlockingServerLock(AbstractContextManager[object]):
    """Translate a non-blocking kernel lock into a server-domain failure."""

    def __init__(self, path: Path, *, server_id: str, busy_error: type[RuntimeError]) -> None:
        self.path = path
        self._lock = InterprocessFileLock(path, blocking=False)
        self._server_id = server_id
        self._busy_error = busy_error

    def __enter__(self) -> object:
        try:
            return self._lock.__enter__()
        except InterprocessLockBusy as exc:
            raise self._busy_error(self._server_id) from exc

    def __exit__(self, exc_type, exc, tb) -> None:
        self._lock.__exit__(exc_type, exc, tb)


class JsonlServerOperationJournal(ServerOperationJournalPort):
    """Append-only local operation ledger for server control-plane actions.

    The ledger is controller-local and contains no credentials or raw remote
    commands.  It stores correlation IDs, request digests, timing, result
    classes and bounded output sizes, so a failed SSH operation can be
    diagnosed without making the server profile or command text a secret
    transport.
    """

    def __init__(self, path: str | Path, *, writer_actor: SerialActorPort) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._guard_path = self.path.with_name(self.path.name + ".guard.lock")
        self._writer_actor = writer_actor

    def _append(self, event_type: str, event: object) -> None:
        """Append and fsync one operation event in ledger order.

        Process-local ordering is owned by the injected serial actor; the
        interprocess guard preserves one durable cross-process append order.
        """
        payload = asdict(event)
        for key, value in tuple(payload.items()):
            if hasattr(value, "value"):
                payload[key] = value.value
        record = {"event": event_type, **payload}
        encoded = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        def append_owned() -> None:
            with InterprocessFileLock(self._guard_path):
                with self.path.open("ab") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())

        self._writer_actor.call(f"append:{event_type}", append_owned)

    @staticmethod
    def _started(payload: dict[str, object]) -> ServerOperationStarted:
        try:
            return ServerOperationStarted(
                str(payload["operation_id"]),
                str(payload["server_id"]),
                ServerOperationKind(str(payload["kind"])),
                str(payload["request_digest"]),
                float(payload["started_at"]),
                bool(payload["interactive"]),
                str(payload.get("profile_digest", "")),
                ServerOperationEffect(str(payload.get("effect", ServerOperationEffect.UNKNOWN.value))),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation started record is malformed"
            ) from exc

    @staticmethod
    def _finished(payload: dict[str, object]) -> ServerOperationFinished:
        try:
            return ServerOperationFinished(
                str(payload["operation_id"]),
                str(payload["server_id"]),
                ServerOperationKind(str(payload["kind"])),
                str(payload["request_digest"]),
                ServerOperationState(str(payload["state"])),
                float(payload["finished_at"]),
                float(payload["duration_seconds"]),
                None if payload.get("return_code") is None else int(payload["return_code"]),
                str(payload["failure_kind"]),
                int(payload["stdout_bytes"]),
                int(payload["stderr_bytes"]),
                None if payload.get("error_type") is None else str(payload["error_type"]),
                None if payload.get("error_digest") is None else str(payload["error_digest"]),
                str(payload.get("profile_digest", "")),
                str(payload.get("stdout_digest", "")),
                str(payload.get("stderr_digest", "")),
                ServerOperationEffect(str(payload.get("effect", ServerOperationEffect.UNKNOWN.value))),
                str(payload.get("stdout_preview", "")),
                str(payload.get("stderr_preview", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation finished record is malformed"
            ) from exc

    @staticmethod
    def _resolved(payload: dict[str, object]) -> ServerOperationResolved:
        try:
            evidence_ref = str(payload["evidence_ref"])
            evidence_digest = str(payload["evidence_digest"])
            if re.fullmatch(r"[A-Za-z0-9_.:/-]{1,256}", evidence_ref) is None:
                raise ValueError("resolution evidence reference is unsafe")
            if re.fullmatch(r"[0-9a-fA-F]{64}", evidence_digest) is None:
                raise ValueError("resolution evidence digest is not SHA-256")
            return ServerOperationResolved(
                str(payload["operation_id"]),
                str(payload["server_id"]),
                ServerOperationKind(str(payload["kind"])),
                str(payload["request_digest"]),
                ServerOperationResolution(str(payload["disposition"])),
                float(payload["resolved_at"]),
                evidence_ref,
                evidence_digest,
                str(payload.get("profile_digest", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServerOperationJournalIntegrityError(
                "server operation resolution record is malformed"
            ) from exc

    def _read_records(self) -> tuple[ServerOperationRecord, ...]:
        """Read one rotation-free and append-free journal snapshot.

        Replay freezes one durable byte prefix through the writer actor and
        validates that immutable prefix outside the writer authority.
        """
        if not self.path.exists():
            return ()
        records: dict[str, ServerOperationRecord] = {}
        order: list[str] = []
        # Freeze only the durable byte boundary under the writer authority.  The
        # journal never rotates, so subsequent appends can only extend this prefix.
        # Parsing the frozen prefix outside the lock removes O(file-size) lock hold.
        def freeze_owned() -> int:
            with InterprocessFileLock(self._guard_path):
                return self.path.stat().st_size

        snapshot_size = self._writer_actor.call("freeze-read-prefix", freeze_owned)
        with self.path.open("rb") as stream:
            remaining = snapshot_size
            line_number = 0
            while remaining > 0:
                raw = stream.readline(remaining)
                if not raw:
                    break
                remaining -= len(raw)
                line_number += 1
                if not raw.strip():
                    continue
                try:
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise TypeError("event is not an object")
                    event_type = payload.pop("event")
                    if event_type == "started":
                        event = self._started(payload)
                        if event.operation_id in records:
                            raise ValueError("duplicate operation start")
                        records[event.operation_id] = ServerOperationRecord(event)
                        order.append(event.operation_id)
                    elif event_type == "finished":
                        event = self._finished(payload)
                        record = records.get(event.operation_id)
                        if record is None or record.finished is not None:
                            raise ValueError("finish has no unique open operation")
                        if (
                            record.started.server_id != event.server_id
                            or record.started.kind != event.kind
                            or record.started.request_digest != event.request_digest
                            or record.started.effect != event.effect
                        ):
                            raise ValueError("finish does not match its start")
                        records[event.operation_id] = ServerOperationRecord(
                            record.started, event, record.resolution
                        )
                    elif event_type == "resolved":
                        event = self._resolved(payload)
                        record = records.get(event.operation_id)
                        if record is None or record.resolution is not None:
                            raise ValueError("resolution has no unique open operation")
                        if (
                            record.started.server_id != event.server_id
                            or record.started.kind != event.kind
                            or record.started.request_digest != event.request_digest
                            or record.started.profile_digest != event.profile_digest
                        ):
                            raise ValueError("resolution does not match its start")
                        if not record.effect_uncertain:
                            raise ValueError("resolution is only valid for an uncertain operation")
                        records[event.operation_id] = ServerOperationRecord(
                            record.started, record.finished, event
                        )
                    else:
                        raise ValueError(f"unknown event type {event_type!r}")
                except ServerOperationJournalIntegrityError as exc:
                    raise ServerOperationJournalIntegrityError(
                        f"server operation ledger is corrupt at line {line_number}"
                    ) from exc
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
                    raise ServerOperationJournalIntegrityError(
                        f"server operation ledger is corrupt at line {line_number}"
                    ) from exc
        return tuple(records[operation_id] for operation_id in order)

    def record_started(self, event: ServerOperationStarted) -> None:
        self._append("started", event)

    def record_finished(self, event: ServerOperationFinished) -> None:
        self._append("finished", event)

    def record_resolved(self, event: ServerOperationResolved) -> None:
        record = self.read_operation(event.operation_id)
        if record is None:
            raise ServerOperationJournalIntegrityError("cannot resolve an unknown server operation")
        if (
            record.server_id != event.server_id
            or record.kind != event.kind
            or record.started.request_digest != event.request_digest
        ):
            raise ServerOperationJournalIntegrityError("server operation resolution identity mismatch")
        if not record.effect_uncertain:
            raise ServerOperationJournalIntegrityError("server operation does not require reconciliation")
        self._append("resolved", event)

    def mutation_lock(self, *, server_id: str) -> AbstractContextManager[object]:
        """Serialize mutating remote operations for one logical server.

        The lock is deliberately separate from the short ledger append lock:
        it remains held across the remote operation, so two controllers cannot
        concurrently prepare/upload/terminate the same server state while both
        still observe an empty pending set. Process exit releases the kernel
        lock; the durable ledger then records the interrupted operation as
        effect-uncertain for the next controller.
        """

        if not server_id:
            raise ValueError("server_id must be non-empty")
        identity = hashlib.sha256(server_id.encode("utf-8")).hexdigest()[:32]
        return _NonBlockingServerLock(
            self.path.with_name(f"{self.path.name}.{identity}.mutation.lock"),
            server_id=server_id,
            busy_error=ServerMutationBusy,
        )

    def transport_lock(self, *, server_id: str) -> AbstractContextManager[object]:
        """Serialize every SSH/SCP attempt for one logical server.

        This is deliberately separate from the mutation lock.  A read-only
        health/status probe must not race an in-flight mutation into a shared
        SSH authentication or ControlMaster channel, but it also must not
        participate in mutation-effect reconciliation.
        """

        if not server_id:
            raise ValueError("server_id must be non-empty")
        identity = hashlib.sha256(server_id.encode("utf-8")).hexdigest()[:32]
        return _NonBlockingServerLock(
            self.path.with_name(f"{self.path.name}.{identity}.transport.lock"),
            server_id=server_id,
            busy_error=ServerTransportBusy,
        )

    def read_operation(self, operation_id: str) -> ServerOperationRecord | None:
        if not operation_id:
            raise ValueError("operation_id must be non-empty")
        return next(
            (record for record in self._read_records() if record.operation_id == operation_id),
            None,
        )

    def pending_operations(
        self,
        *,
        server_id: str | None = None,
    ) -> tuple[ServerOperationRecord, ...]:
        """Return operations whose remote effect is not durably known.

        This is a reconciliation signal, not a retry queue.  A caller must
        inspect the remote effect and record a resolution before submitting a
        mutating operation again.
        """

        return tuple(
            record
            for record in self._read_records()
            if record.effect_uncertain
            and (server_id is None or record.server_id == server_id)
        )

    def recent_operations(
        self,
        limit: int = 20,
        *,
        server_id: str | None = None,
    ) -> tuple[ServerOperationRecord, ...]:
        if limit <= 0:
            raise ValueError("operation history limit must be positive")
        records = tuple(
            record
            for record in self._read_records()
            if server_id is None or record.server_id == server_id
        )
        return tuple(reversed(records[-limit:]))


__all__ = ["JsonlServerOperationJournal", "ServerOperationJournalIntegrityError"]
