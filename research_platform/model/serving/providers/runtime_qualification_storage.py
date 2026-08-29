from __future__ import annotations

import hashlib
import os
from pathlib import Path
from threading import Lock

from research_platform.platform.kernel.durability import (
    ChecksummedDocumentError,
    decode_checksummed_document,
    encode_checksummed_document,
)
from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes
from research_platform.platform.kernel.durability.file_lock import InterprocessFileLock

from ..api.runtime_qualification import RuntimeQualificationReceipt


_SCHEMA = "runtime-qualification-receipt.v2"
_RECEIPT_FIELDS = frozenset(
    {
        "deployment_id",
        "stack_digest",
        "qualification_certificate_digest",
        "heartbeat_qualification_digest",
        "qualified_roles",
        "evidence_refs",
        "created_at",
    }
)
_PAYLOAD_FIELDS = frozenset({"receipt", "receipt_digest"})
_LOCAL_LOCKS_GUARD = Lock()
_LOCAL_LOCKS: dict[str, Lock] = {}


class RuntimeQualificationEvidenceError(RuntimeError):
    """Durable runtime-qualification evidence is malformed or conflicting."""


def _require_digest(value: object, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise RuntimeQualificationEvidenceError(f"{field} must be lowercase SHA-256")
    return value


def _local_lock(path: Path) -> Lock:
    key = os.path.normcase(str(path.resolve(strict=False)))
    with _LOCAL_LOCKS_GUARD:
        lock = _LOCAL_LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _LOCAL_LOCKS[key] = lock
        return lock


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise RuntimeQualificationEvidenceError(f"{field} must be a non-empty JSON array")
    if any(type(item) is not str or not item.strip() for item in value):
        raise RuntimeQualificationEvidenceError(f"{field} values must be non-empty strings")
    return tuple(value)


def _encode_receipt(receipt: RuntimeQualificationReceipt) -> bytes:
    payload = {
        "receipt": {
            "deployment_id": receipt.deployment_id,
            "stack_digest": receipt.stack_digest,
            "qualification_certificate_digest": receipt.qualification_certificate_digest,
            "heartbeat_qualification_digest": receipt.heartbeat_qualification_digest,
            "qualified_roles": list(receipt.qualified_roles),
            "evidence_refs": list(receipt.evidence_refs),
            "created_at": receipt.created_at,
        },
        "receipt_digest": receipt.digest(),
    }
    return encode_checksummed_document(_SCHEMA, payload)


def _decode_receipt(raw: bytes) -> RuntimeQualificationReceipt:
    try:
        payload = decode_checksummed_document(raw, expected_schema=_SCHEMA).payload
    except ChecksummedDocumentError as exc:
        raise RuntimeQualificationEvidenceError("runtime qualification document integrity failure") from exc
    if frozenset(payload) != _PAYLOAD_FIELDS:
        raise RuntimeQualificationEvidenceError("runtime qualification payload field set mismatch")
    receipt_raw = payload.get("receipt")
    if not isinstance(receipt_raw, dict) or frozenset(receipt_raw) != _RECEIPT_FIELDS:
        raise RuntimeQualificationEvidenceError("runtime qualification receipt field set mismatch")
    created_at = receipt_raw.get("created_at")
    if type(created_at) is not float:
        raise RuntimeQualificationEvidenceError("runtime qualification created_at must be a JSON float")
    try:
        receipt = RuntimeQualificationReceipt(
            deployment_id=receipt_raw.get("deployment_id"),
            stack_digest=_require_digest(receipt_raw.get("stack_digest"), "stack_digest"),
            qualification_certificate_digest=_require_digest(
                receipt_raw.get("qualification_certificate_digest"),
                "qualification_certificate_digest",
            ),
            heartbeat_qualification_digest=_require_digest(
                receipt_raw.get("heartbeat_qualification_digest"),
                "heartbeat_qualification_digest",
            ),
            qualified_roles=_string_list(receipt_raw.get("qualified_roles"), "qualified_roles"),
            evidence_refs=_string_list(receipt_raw.get("evidence_refs"), "evidence_refs"),
            created_at=created_at,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeQualificationEvidenceError("runtime qualification receipt is invalid") from exc
    expected_digest = _require_digest(payload.get("receipt_digest"), "receipt_digest")
    if receipt.digest() != expected_digest:
        raise RuntimeQualificationEvidenceError("runtime qualification receipt digest mismatch")
    return receipt


class DirectoryRuntimeQualificationEvidenceStore:
    """Directory backend for immutable, checksummed runtime-qualification receipts."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, runtime_manifest_digest: str, deployment_id: str) -> Path:
        manifest = _require_digest(runtime_manifest_digest, "runtime_manifest_digest")
        if type(deployment_id) is not str or not deployment_id.strip():
            raise RuntimeQualificationEvidenceError("deployment_id is required")
        deployment_key = hashlib.sha256(deployment_id.encode("utf-8")).hexdigest()
        return self.root / manifest / f"{deployment_key}.json"

    def publish(self, runtime_manifest_digest: str, receipt: RuntimeQualificationReceipt) -> str:
        path = self._path(runtime_manifest_digest, receipt.deployment_id)
        lock_path = path.with_name(path.name + ".lock")
        raw = _encode_receipt(receipt)
        with _local_lock(lock_path):
            with InterprocessFileLock(lock_path):
                if path.exists():
                    existing = _decode_receipt(path.read_bytes())
                    if existing != receipt:
                        raise RuntimeQualificationEvidenceError(
                            "runtime qualification receipt already exists with different evidence"
                        )
                    return str(path)
                atomic_replace_bytes(path, raw)
                persisted = _decode_receipt(path.read_bytes())
                if persisted != receipt:
                    raise RuntimeQualificationEvidenceError("runtime qualification receipt readback drift")
                return str(path)

    def load(self, runtime_manifest_digest: str, deployment_id: str) -> RuntimeQualificationReceipt:
        path = self._path(runtime_manifest_digest, deployment_id)
        try:
            receipt = _decode_receipt(path.read_bytes())
        except OSError as exc:
            raise RuntimeQualificationEvidenceError(
                f"runtime qualification receipt cannot be read: {path}"
            ) from exc
        if receipt.deployment_id != deployment_id:
            raise RuntimeQualificationEvidenceError("runtime qualification deployment identity drift")
        return receipt


__all__ = [
    "DirectoryRuntimeQualificationEvidenceStore",
    "RuntimeQualificationEvidenceError",
]
