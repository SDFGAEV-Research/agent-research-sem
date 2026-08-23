from __future__ import annotations

import threading

import pytest

from projects.sem_paper.method.self_evolving_memory.session_state_memory import (
    InMemorySEMSessionStateFactory,
)


class _PreparedAdoption:
    def __init__(self, generation: str, *, entered=None, release=None, failure=None) -> None:
        self.generation = generation
        self.entered = entered
        self.release = release
        self.failure = failure
        self.calls = 0

    def commit(self) -> str:
        self.calls += 1
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            assert self.release.wait(timeout=2)
        if self.failure is not None:
            raise self.failure
        return self.generation


def test_prepared_adoption_advances_generation_and_lineage_once() -> None:
    cell = InMemorySEMSessionStateFactory().create("authority-success")
    adoption = _PreparedAdoption("g1")

    generation, record = cell.commit_prepared_adoption(adoption)

    assert generation == "g1"
    assert adoption.calls == 1
    assert cell.current_generation() == "g1"
    assert cell.evolution_summary()[-1] == 1
    assert record.mutation_type == "ADOPTION_COMMIT"
    assert record.architecture_generation == "g1"


def test_failed_prepared_adoption_does_not_publish_generation() -> None:
    cell = InMemorySEMSessionStateFactory().create("authority-failure")
    adoption = _PreparedAdoption("g1", failure=RuntimeError("durable commit failed"))

    with pytest.raises(RuntimeError, match="durable commit failed"):
        cell.commit_prepared_adoption(adoption)

    assert cell.current_generation() == "g0"
    assert cell.evolution_summary()[-1] == 0
    assert cell.mutation_history() == ()


def test_serving_cut_cannot_interleave_between_commit_and_publication() -> None:
    cell = InMemorySEMSessionStateFactory().create("authority-serialization")
    entered = threading.Event()
    release = threading.Event()
    adoption = _PreparedAdoption("g1", entered=entered, release=release)
    adopted: list[str] = []
    observed: list[str] = []

    commit_thread = threading.Thread(
        target=lambda: adopted.append(cell.commit_prepared_adoption(adoption)[0])
    )
    commit_thread.start()
    assert entered.wait(timeout=2)

    read_thread = threading.Thread(target=lambda: observed.append(cell.open_serving_cut()[0]))
    read_thread.start()
    assert read_thread.is_alive()

    release.set()
    commit_thread.join(timeout=2)
    read_thread.join(timeout=2)

    assert adopted == ["g1"]
    assert observed == ["g1"]
