from __future__ import annotations

from dataclasses import asdict
from typing import Any

from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodObservation

from .evidence_api import EvidenceRecord, EvidenceSnapshot
from .session_reducer import SEMSessionState
from .session_snapshot_contracts import SEMSessionStateSnapshot, SEMSnapshotPayload, SessionLineageSnapshot, SessionMutationRecord
from .task_lifecycle import TaskPhase, TaskProgress


def snapshot_document(payload: SEMSnapshotPayload) -> dict[str, Any]:
    session_state = payload.session_state
    return {
        "state": asdict(session_state.state),
        "lineage": {
            "revision": session_state.lineage.revision,
            "mutation_tail": [asdict(row) for row in session_state.lineage.mutation_tail],
        },
        "task_progress": [
            {
                "task_key": row.task_key,
                "phase": row.phase.value,
                "base_generation": row.base_generation,
                "final_generation": row.final_generation,
                "terminal_reason": row.terminal_reason,
            }
            for row in payload.task_progress
        ],
        "pending_observations": [
            {
                "observation_id": row.observation_id,
                "context": asdict(row.context),
                "method_id": row.method_id,
                "session_id": row.session_id,
                "kind": row.kind,
                "payload": dict(row.payload),
            }
            for row in payload.pending_observations
        ],
        "evidence": {
            "sequence": session_state.evidence.sequence,
            "digest": session_state.evidence.digest,
            "rows": [asdict(row) for row in session_state.evidence.rows],
        },
    }


def payload_from_document(data: dict[str, Any]) -> SEMSnapshotPayload:
    state = SEMSessionState(**data["state"])
    evidence_data = data["evidence"]
    evidence = EvidenceSnapshot(
        sequence=int(evidence_data["sequence"]),
        rows=tuple(
            EvidenceRecord(
                evidence_id=row["evidence_id"],
                sequence=int(row["sequence"]),
                payload=row["payload"],
                digest=row["digest"],
            )
            for row in evidence_data["rows"]
        ),
        digest=evidence_data["digest"],
    )
    lineage_data = data["lineage"]
    lineage = SessionLineageSnapshot(
        revision=int(lineage_data["revision"]),
        mutation_tail=tuple(SessionMutationRecord(**row) for row in lineage_data["mutation_tail"]),
    )
    pending = tuple(
        MethodObservation(
            row["observation_id"],
            ExecutionContext(**row["context"]),
            row["method_id"],
            row["session_id"],
            row["kind"],
            row["payload"],
        )
        for row in data["pending_observations"]
    )
    task_progress = tuple(
        TaskProgress(
            task_key=str(row["task_key"]),
            phase=TaskPhase(str(row["phase"])),
            base_generation=str(row["base_generation"]),
            final_generation=(str(row["final_generation"]) if row.get("final_generation") is not None else None),
            terminal_reason=(str(row["terminal_reason"]) if row.get("terminal_reason") is not None else None),
        )
        for row in data.get("task_progress", ())
    )
    return SEMSnapshotPayload(SEMSessionStateSnapshot(state, evidence, lineage), pending, task_progress)
