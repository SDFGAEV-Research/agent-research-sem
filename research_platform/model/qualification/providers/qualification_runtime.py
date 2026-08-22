"""Checksummed storage for post-materialization runtime qualification."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from research_platform.model.qualification.api import (
    DeploymentQualificationRuntimeReceipt,
    DeploymentQualificationRuntimeStorePort,
    DeploymentRuntimeQualificationStatus,
    RuntimeCheckReceipt,
)
from research_platform.platform.kernel import canonical_bytes
from research_platform.platform.kernel.durability import (
    ChecksummedDocumentError,
    atomic_replace_bytes,
    decode_checksummed_document,
    encode_checksummed_document,
)


_SCHEMA = "model-deployment-qualification-runtime.v1"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class QualificationRuntimeIntegrityError(RuntimeError):
    """Raised when a runtime qualification receipt is malformed or altered."""


class FileDeploymentQualificationRuntimeStore(DeploymentQualificationRuntimeStorePort):
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        receipt: DeploymentQualificationRuntimeReceipt,
    ) -> DeploymentQualificationRuntimeReceipt:
        atomic_replace_bytes(
            self._path(receipt.runtime_digest),
            encode_checksummed_document(_SCHEMA, self._payload(receipt)),
        )
        return receipt

    def get(self, runtime_digest: str) -> DeploymentQualificationRuntimeReceipt:
        if _DIGEST_RE.fullmatch(runtime_digest) is None:
            raise ValueError("runtime qualification digest must be a lowercase SHA-256 digest")
        path = self._path(runtime_digest)
        if not path.is_file():
            raise KeyError(runtime_digest)
        try:
            document = decode_checksummed_document(path.read_bytes(), expected_schema=_SCHEMA)
            receipt = self._receipt(document.payload)
        except (ChecksummedDocumentError, KeyError, TypeError, ValueError, OSError) as exc:
            raise QualificationRuntimeIntegrityError(
                f"invalid runtime qualification record: {runtime_digest}"
            ) from exc
        if receipt.runtime_digest != runtime_digest:
            raise QualificationRuntimeIntegrityError(
                f"runtime qualification digest mismatch: {runtime_digest}"
            )
        return receipt

    def _path(self, digest: str) -> Path:
        return self._root / f"{digest}.json"

    @staticmethod
    def _payload(receipt: DeploymentQualificationRuntimeReceipt) -> dict[str, Any]:
        return json.loads(canonical_bytes(receipt).decode("utf-8"))

    @staticmethod
    def _check(data: dict[str, Any]) -> RuntimeCheckReceipt:
        return RuntimeCheckReceipt(
            check=str(data["check"]),
            command_digest=str(data["command_digest"]),
            return_code=int(data["return_code"]),
            stdout_digest=str(data["stdout_digest"]),
            stderr_digest=str(data["stderr_digest"]),
        )

    @classmethod
    def _receipt(cls, payload: dict[str, Any]) -> DeploymentQualificationRuntimeReceipt:
        receipt = DeploymentQualificationRuntimeReceipt(
            application_digest=str(payload["application_digest"]),
            plan_digest=str(payload["plan_digest"]),
            environment_id=str(payload["environment_id"]),
            backend=str(payload["backend"]) if payload.get("backend") else None,
            checks=tuple(cls._check(item) for item in payload.get("checks", ())),
            status=DeploymentRuntimeQualificationStatus(str(payload["status"])),
            reasons=tuple(str(item) for item in payload.get("reasons", ())),
        )
        if receipt.runtime_digest != str(payload.get("runtime_digest", "")):
            raise QualificationRuntimeIntegrityError("runtime qualification digest mismatch")
        return receipt


__all__ = [
    "FileDeploymentQualificationRuntimeStore",
    "QualificationRuntimeIntegrityError",
]
