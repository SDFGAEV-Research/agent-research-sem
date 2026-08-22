"""Checksummed storage for qualification-plan materialization receipts."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from research_platform.model.qualification.api import (
    DeploymentQualificationApplicationReceipt,
    DeploymentQualificationApplicationStorePort,
    InstallPackage,
    QualificationCommandReceipt,
    QualificationMaterializationStatus,
)
from research_platform.platform.kernel import canonical_bytes
from research_platform.platform.kernel.durability import (
    ChecksummedDocumentError,
    atomic_replace_bytes,
    decode_checksummed_document,
    encode_checksummed_document,
)


_SCHEMA = "model-deployment-qualification-application.v1"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class QualificationApplicationIntegrityError(RuntimeError):
    """Raised when a materialization receipt is malformed or altered."""


class FileDeploymentQualificationApplicationStore(DeploymentQualificationApplicationStorePort):
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        receipt: DeploymentQualificationApplicationReceipt,
    ) -> DeploymentQualificationApplicationReceipt:
        atomic_replace_bytes(
            self._path(receipt.application_digest),
            encode_checksummed_document(_SCHEMA, self._payload(receipt)),
        )
        return receipt

    def get(self, application_digest: str) -> DeploymentQualificationApplicationReceipt:
        if _DIGEST_RE.fullmatch(application_digest) is None:
            raise ValueError("qualification application digest must be a lowercase SHA-256 digest")
        path = self._path(application_digest)
        if not path.is_file():
            raise KeyError(application_digest)
        try:
            document = decode_checksummed_document(path.read_bytes(), expected_schema=_SCHEMA)
            receipt = self._receipt(document.payload)
        except (ChecksummedDocumentError, KeyError, TypeError, ValueError, OSError) as exc:
            raise QualificationApplicationIntegrityError(
                f"invalid qualification application record: {application_digest}"
            ) from exc
        if receipt.application_digest != application_digest:
            raise QualificationApplicationIntegrityError(
                f"qualification application digest mismatch: {application_digest}"
            )
        return receipt

    def _path(self, digest: str) -> Path:
        return self._root / f"{digest}.json"

    @staticmethod
    def _payload(receipt: DeploymentQualificationApplicationReceipt) -> dict[str, Any]:
        return json.loads(canonical_bytes(receipt).decode("utf-8"))

    @staticmethod
    def _command(data: dict[str, Any] | None) -> QualificationCommandReceipt | None:
        if data is None:
            return None
        return QualificationCommandReceipt(
            operation=str(data["operation"]),
            command_digest=str(data["command_digest"]),
            return_code=int(data["return_code"]),
            stdout_digest=str(data["stdout_digest"]),
            stderr_digest=str(data["stderr_digest"]),
        )

    @classmethod
    def _receipt(cls, payload: dict[str, Any]) -> DeploymentQualificationApplicationReceipt:
        receipt = DeploymentQualificationApplicationReceipt(
            plan_digest=str(payload["plan_digest"]),
            environment_id=str(payload["environment_id"]),
            backend=str(payload["backend"]) if payload.get("backend") else None,
            packages=tuple(
                InstallPackage(
                    name=str(item["name"]),
                    version=str(item["version"]),
                    index_url=str(item["index_url"]),
                )
                for item in payload.get("packages", ())
            ),
            install_commands=tuple(cls._command(item) for item in payload.get("install_commands", ())),
            check_command=cls._command(payload.get("check_command")),
            status=QualificationMaterializationStatus(str(payload["status"])),
            reasons=tuple(str(item) for item in payload.get("reasons", ())),
        )
        if receipt.application_digest != str(payload.get("application_digest", "")):
            raise QualificationApplicationIntegrityError("qualification application digest mismatch")
        return receipt


__all__ = [
    "FileDeploymentQualificationApplicationStore",
    "QualificationApplicationIntegrityError",
]
