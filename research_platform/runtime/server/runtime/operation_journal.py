from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
from threading import Lock

from research_platform.runtime.server.api import (
    ServerOperationFinished,
    ServerOperationJournalPort,
    ServerOperationStarted,
)


class JsonlServerOperationJournal(ServerOperationJournalPort):
    """Append-only local operation ledger for server control-plane actions.

    The ledger is controller-local and contains no credentials or raw remote
    commands.  It stores correlation IDs, request digests, timing, result
    classes and bounded output sizes, so a failed SSH operation can be
    diagnosed without making the server profile or command text a secret
    transport.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _append(self, event_type: str, event: object) -> None:
        payload = asdict(event)
        for key, value in tuple(payload.items()):
            if hasattr(value, "value"):
                payload[key] = value.value
        record = {"event": event_type, **payload}
        encoded = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        with self._lock:
            with self.path.open("ab") as stream:
                try:
                    import fcntl
                except ImportError:
                    fcntl = None
                if fcntl is not None:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                finally:
                    if fcntl is not None:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def record_started(self, event: ServerOperationStarted) -> None:
        self._append("started", event)

    def record_finished(self, event: ServerOperationFinished) -> None:
        self._append("finished", event)


__all__ = ["JsonlServerOperationJournal"]
