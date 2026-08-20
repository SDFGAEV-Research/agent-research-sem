from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class SEMSessionState:
    architecture_generation: str
    evidence_sequence: int
    evolution_epoch: int
    tasks_completed: int
    last_grounded_payload: str


def initial_session_state() -> SEMSessionState:
    return SEMSessionState(
        architecture_generation="g0",
        evidence_sequence=0,
        evolution_epoch=0,
        tasks_completed=0,
        last_grounded_payload="",
    )


def after_ingest(state: SEMSessionState, *, sequence: int, grounded_payload: str) -> SEMSessionState:
    if sequence != state.evidence_sequence + 1:
        raise ValueError("SEM evidence sequence must advance by exactly one")
    return replace(
        state,
        evidence_sequence=sequence,
        last_grounded_payload=grounded_payload,
    )


def after_task_completed(state: SEMSessionState) -> SEMSessionState:
    return replace(state, tasks_completed=state.tasks_completed + 1)


def after_adoption(state: SEMSessionState, *, generation: str) -> SEMSessionState:
    if not generation:
        raise ValueError("SEM adopted generation must be non-empty")
    if generation == state.architecture_generation:
        raise ValueError("SEM adoption must advance architecture generation")
    return replace(
        state,
        architecture_generation=generation,
        evolution_epoch=state.evolution_epoch + 1,
    )
