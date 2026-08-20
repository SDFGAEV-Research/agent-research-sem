from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvalEvidence:
    eval_id: str
    payload: object


class EvalEvidenceStore:
    """J_eval authority. Private evaluation evidence cannot materialize method memory."""

    def __init__(self) -> None:
        self._rows: list[EvalEvidence] = []

    def append(self, row: EvalEvidence) -> None:
        self._rows.append(row)
