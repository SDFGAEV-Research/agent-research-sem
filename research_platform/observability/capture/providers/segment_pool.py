from __future__ import annotations

from pathlib import Path
from threading import RLock

from .segment_writer import RawSegmentWriter


class RawSegmentPool:
    """Short-lock registry for actor-owned raw segment writers."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = RLock()
        self._writers: dict[tuple[str, str], RawSegmentWriter] = {}
        self._closed = False

    @staticmethod
    def target(root: Path, run_id: str, family: str) -> Path:
        safe_family = family.replace("/", "_").replace(".", "_")
        return root / run_id / f"{safe_family}.jsonl"

    def get(self, run_id: str, family: str, schema_version: str) -> RawSegmentWriter:
        key = (run_id, family)
        with self._lock:
            if self._closed:
                raise RuntimeError("raw segment pool is closed")
            existing = self._writers.get(key)
            if existing is not None:
                if existing.schema_version != schema_version:
                    raise ValueError(
                        f"raw segment schema drift for {key}: "
                        f"{existing.schema_version} != {schema_version}"
                    )
                return existing

        # Recovery/open can touch the filesystem and is intentionally outside
        # the registry lock.  Per-segment actor ownership serializes same-key
        # creation; the second check is defensive against programming mistakes.
        candidate = RawSegmentWriter(
            self.target(self.root, run_id, family),
            family,
            schema_version,
            run_id,
        )
        discard: RawSegmentWriter | None = None
        try:
            with self._lock:
                if self._closed:
                    discard = candidate
                    raise RuntimeError("raw segment pool is closed")
                existing = self._writers.get(key)
                if existing is None:
                    self._writers[key] = candidate
                    return candidate
                if existing.schema_version != schema_version:
                    discard = candidate
                    raise ValueError(
                        f"raw segment schema drift for {key}: "
                        f"{existing.schema_version} != {schema_version}"
                    )
                discard = candidate
                return existing
        finally:
            if discard is not None:
                discard.close()

    def seal(self) -> tuple[tuple[tuple[str, str], RawSegmentWriter], ...]:
        with self._lock:
            if self._closed:
                return ()
            self._closed = True
            return tuple(self._writers.items())
