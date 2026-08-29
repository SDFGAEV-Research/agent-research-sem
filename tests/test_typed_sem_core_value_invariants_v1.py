from __future__ import annotations

import pytest

from projects.sem_paper.method.self_evolving_memory.evidence_api import (
    EvidenceCut,
    EvidenceRecord,
    EvidenceSnapshot,
)
from projects.sem_paper.method.self_evolving_memory.session_reducer import SEMSessionState
from projects.sem_paper.method.self_evolving_memory.session_snapshot_contracts import (
    SEMSessionStateSnapshot,
    SessionLineageSnapshot,
    SessionMutationRecord,
)
from projects.sem_paper.method.self_evolving_memory.task_lifecycle import TaskPhase, TaskProgress


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _state(**overrides: object) -> SEMSessionState:
    values: dict[str, object] = {
        "architecture_generation": "g0",
        "evidence_sequence": 0,
        "evolution_epoch": 0,
        "tasks_completed": 0,
        "last_grounded_payload": "",
    }
    values.update(overrides)
    return SEMSessionState(**values)  # type: ignore[arg-type]


def _mutation(**overrides: object) -> SessionMutationRecord:
    values: dict[str, object] = {
        "revision": 1,
        "mutation_type": "INGEST",
        "before_state_digest": DIGEST_A,
        "after_state_digest": DIGEST_B,
        "before_evidence_digest": DIGEST_A,
        "after_evidence_digest": DIGEST_B,
        "before_closed": False,
        "after_closed": False,
        "evidence_sequence": 1,
        "architecture_generation": "g0",
    }
    values.update(overrides)
    return SessionMutationRecord(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    (
        {"architecture_generation": ""},
        {"evidence_sequence": True},
        {"evolution_epoch": -1},
        {"tasks_completed": 1.0},
        {"last_grounded_payload": None},
    ),
)
def test_sem_session_state_rejects_invalid_scalar_identity(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _state(**overrides)


def test_evidence_values_reject_invalid_identity_and_shape() -> None:
    with pytest.raises(ValueError, match="evidence_id"):
        EvidenceRecord("", 1, {}, DIGEST_A)
    with pytest.raises(ValueError, match="positive integer"):
        EvidenceRecord("e1", True, {}, DIGEST_A)
    with pytest.raises(ValueError, match="SHA-256"):
        EvidenceRecord("e1", 1, {}, "A" * 64)
    with pytest.raises(ValueError, match="sequence/count"):
        EvidenceCut(1, 0, DIGEST_A)
    with pytest.raises(ValueError, match="rows must be a tuple"):
        EvidenceSnapshot(0, [], DIGEST_A)  # type: ignore[arg-type]


def test_evidence_snapshot_sequence_must_match_final_row() -> None:
    row = EvidenceRecord("e1", 1, {}, DIGEST_A)
    with pytest.raises(ValueError, match="final evidence row"):
        EvidenceSnapshot(2, (row,), DIGEST_B)


@pytest.mark.parametrize(
    "row",
    (
        lambda: TaskProgress("", TaskPhase.OBSERVATION_PENDING, "g0"),
        lambda: TaskProgress("task", "completed", "g0"),  # type: ignore[arg-type]
        lambda: TaskProgress("task", TaskPhase.OBSERVATION_PENDING, ""),
        lambda: TaskProgress("task", TaskPhase.ADOPTION_OBSERVATION_PENDING, "g0"),
        lambda: TaskProgress("task", TaskPhase.EVOLUTION_PENDING, "g0", final_generation="g1"),
        lambda: TaskProgress("task", TaskPhase.EVOLUTION_UNCERTAIN, "g0", terminal_reason="failed"),
    ),
)
def test_task_progress_rejects_impossible_value_states(row) -> None:
    with pytest.raises(ValueError):
        row()


def test_task_progress_accepts_adoption_and_terminal_states() -> None:
    pending = TaskProgress("task", TaskPhase.ADOPTION_OBSERVATION_PENDING, "g0", final_generation="g1")
    completed = TaskProgress("task", TaskPhase.COMPLETED, "g0", terminal_reason="no_adoption")
    assert pending.final_generation == "g1"
    assert completed.terminal_reason == "no_adoption"


@pytest.mark.parametrize(
    "overrides",
    (
        {"revision": True},
        {"mutation_type": ""},
        {"before_state_digest": "bad"},
        {"before_closed": 1},
        {"evidence_sequence": True},
        {"architecture_generation": ""},
        {"source_revision": True},
        {"run_id": 7},
    ),
)
def test_session_mutation_record_rejects_invalid_scalar_fields(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _mutation(**overrides)


def test_session_state_snapshot_rejects_cross_authority_sequence_drift() -> None:
    evidence = EvidenceSnapshot(0, (), DIGEST_A)
    lineage = SessionLineageSnapshot(0, ())
    with pytest.raises(ValueError, match="state/evidence sequence mismatch"):
        SEMSessionStateSnapshot(_state(evidence_sequence=1), evidence, lineage)
