from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditEvidence:
    audit_id: str
    payload: object


class AuditEvidenceStore:
    """J_audit authority. No J_mem view or materialization capability is exposed."""

    def __init__(self) -> None:
        self._rows: list[AuditEvidence] = []

    def append(self, row: AuditEvidence) -> None:
        self._rows.append(row)
