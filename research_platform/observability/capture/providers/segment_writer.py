from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from ..api.contracts import RawObservationReceipt
from .segment_recovery import recover_raw_segment


@dataclass(frozen=True, slots=True)
class SegmentWriterState:
    sequence: int
    closed: bool


class RawSegmentWriter:
    """Actor-owned append writer for one raw-observation segment.

    Serialization is provided by the owning serial actor.  The writer therefore
    contains no Python lock and never performs blocking I/O while a caller-owned
    mutex is held.
    """

    def __init__(self, target: Path, family: str, schema_version: str, run_id: str) -> None:
        self.target = target
        self.family = family
        self.schema_version = schema_version
        self.run_id = run_id
        target.parent.mkdir(parents=True, exist_ok=True)
        recovered = recover_raw_segment(
            target,
            family=family,
            schema_version=schema_version,
            run_id=run_id,
        )
        self.idempotency = recovered.idempotency
        self._state = SegmentWriterState(recovered.sequence, False)
        flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
        if os.name == "nt":
            flags |= getattr(os, "O_BINARY", 0)
        self._flags = flags
        self._fd = None if os.name == "nt" else os.open(target, flags, 0o644)

    @property
    def sequence(self) -> int:
        return self._state.sequence

    @staticmethod
    def _write_all(fd: int, encoded: bytes) -> None:
        view = memoryview(encoded)
        total = 0
        while total < len(view):
            written = os.write(fd, view[total:])
            if written <= 0:
                raise OSError("raw segment write returned zero bytes")
            total += written

    def previous(self, idempotency_key: str) -> RawObservationReceipt | None:
        return self.idempotency.get(idempotency_key)

    def append(self, encoded: bytes, receipt: RawObservationReceipt, idempotency_key: str | None) -> None:
        if self._state.closed:
            raise RuntimeError("raw segment writer is closed")
        if os.name == "nt":
            fd = os.open(self.target, self._flags, 0o644)
            try:
                self._write_all(fd, encoded)
            finally:
                os.close(fd)
        else:
            assert self._fd is not None
            self._write_all(self._fd, encoded)
        self._state = SegmentWriterState(receipt.sequence, False)
        if idempotency_key is not None:
            self.idempotency[idempotency_key] = receipt

    def close(self) -> None:
        if self._state.closed:
            return
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._state = SegmentWriterState(self._state.sequence, True)
