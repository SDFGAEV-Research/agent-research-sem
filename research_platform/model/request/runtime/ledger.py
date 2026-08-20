from __future__ import annotations

import json
import hashlib
import fcntl
from pathlib import Path
from dataclasses import asdict

from research_platform.platform.kernel import ExecutionContext, ImmutableModelIdentity
from research_platform.model.request.api import ContentRef, ModelRequestEnvelope
from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes


class DirectoryModelRequestLedger:
    """Append-only-by-identity request ledger: request_id may bind exactly one envelope."""

    durability = "crash_durable"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe(request_id: str) -> str:
        return hashlib.sha256(request_id.encode("utf-8")).hexdigest()

    def _path(self, request_id: str) -> Path:
        return self.root / f"{self._safe(request_id)}.json"

    def _lock_path(self, request_id: str) -> Path:
        return self.root / f"{self._safe(request_id)}.lock"

    @staticmethod
    def _encode(envelope: ModelRequestEnvelope) -> bytes:
        return json.dumps(asdict(envelope), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _ref(data: dict[str, object] | None) -> ContentRef | None:
        return None if data is None else ContentRef(**data)

    @classmethod
    def _decode(cls, payload: bytes) -> ModelRequestEnvelope:
        data = json.loads(payload)
        data["context"] = ExecutionContext(**data["context"])
        data["model"] = ImmutableModelIdentity(**data["model"])
        data["request_body"] = cls._ref(data["request_body"])
        data["compiled_prompt"] = cls._ref(data.get("compiled_prompt"))
        data["tool_schema_bundle"] = cls._ref(data.get("tool_schema_bundle"))
        data["source_artifact_refs"] = tuple(data.get("source_artifact_refs", ()))
        data["source_state_refs"] = tuple(data.get("source_state_refs", ()))
        return ModelRequestEnvelope(**data)

    def append(self, envelope: ModelRequestEnvelope) -> None:
        path = self._path(envelope.request_id)
        encoded = self._encode(envelope)
        lock_path = self._lock_path(envelope.request_id)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                if path.exists():
                    current = self._decode(path.read_bytes())
                    if current != envelope:
                        raise RuntimeError("model request id is already bound to a different envelope")
                    return
                atomic_replace_bytes(path, encoded)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def get(self, request_id: str) -> ModelRequestEnvelope:
        envelope = self._decode(self._path(request_id).read_bytes())
        if envelope.request_id != request_id:
            raise RuntimeError("model request lookup identity mismatch")
        return envelope


__all__ = ["DirectoryModelRequestLedger"]
