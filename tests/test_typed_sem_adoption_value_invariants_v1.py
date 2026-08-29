from __future__ import annotations

import pytest

from research_platform.data.state.api import AggregateValue, AtomicMutation
from projects.sem_paper.method.self_evolving_memory.adoption_types import (
    AdoptionBaseState,
    EvolutionLedgerEntry,
    MaterializedCandidate,
    PreparedAdoption,
)
from projects.sem_paper.method.self_evolving_memory.materialization import (
    MaterializationContract,
    PreparedGeneration,
    PreparedStatus,
)


SOURCE_DIGEST = "a" * 64


def _prepared(*, generation: str = "g2", candidate_id: str = "candidate") -> PreparedGeneration:
    return PreparedGeneration(
        generation=generation,
        base_generation="g1",
        candidate_id=candidate_id,
        source_sequence=1,
        source_snapshot_digest=SOURCE_DIGEST,
        target_spec_digest="spec",
        records=(("node", "record"),),
    )


def _entry(*, generation: str = "g2", candidate_id: str = "candidate") -> EvolutionLedgerEntry:
    return EvolutionLedgerEntry(
        candidate_id=candidate_id,
        base_generation="g1",
        adopted_generation=generation,
        evaluation_pair_id="pair",
        target_spec_digest="spec",
        source_snapshot_digest=SOURCE_DIGEST,
        source_sequence=1,
    )


def _mutation(aggregate_id: str, *, generation: str = "g2") -> AtomicMutation:
    return AtomicMutation(aggregate_id, 1, "g1", generation, "b" * 64, {})


def _adoption(**overrides: object) -> PreparedAdoption:
    values: dict[str, object] = {
        "generation": "g2",
        "prepared_generation": _prepared(),
        "architecture_mutation": _mutation("architecture"),
        "ledger_mutation": _mutation("ledger"),
        "ledger_entry": _entry(),
    }
    values.update(overrides)
    return PreparedAdoption(**values)  # type: ignore[arg-type]


def test_materialization_contract_requires_node_identity() -> None:
    with pytest.raises(ValueError, match="node_id"):
        MaterializationContract("", {}, {})


@pytest.mark.parametrize(
    "overrides",
    (
        {"generation": ""},
        {"source_sequence": True},
        {"source_snapshot_digest": "bad"},
        {"records": [("node", "record")]},
        {"records": (("node", ""),)},
        {"status": "prepared"},
    ),
)
def test_prepared_generation_rejects_invalid_identity_and_shape(overrides: dict[str, object]) -> None:
    values = {
        "generation": "g2",
        "base_generation": "g1",
        "candidate_id": "candidate",
        "source_sequence": 1,
        "source_snapshot_digest": SOURCE_DIGEST,
        "target_spec_digest": "spec",
        "records": (("node", "record"),),
        "status": PreparedStatus.PREPARED,
    }
    values.update(overrides)
    with pytest.raises(ValueError):
        PreparedGeneration(**values)  # type: ignore[arg-type]


def test_prepared_generation_rejects_typed_generation_identity_drift() -> None:
    class Typed:
        generation = "other"

    with pytest.raises(ValueError, match="typed materialized generation identity"):
        PreparedGeneration("g2", "g1", "candidate", 1, SOURCE_DIGEST, "spec", (), typed_generation=Typed())


@pytest.mark.parametrize(
    "overrides",
    (
        {"candidate_id": ""},
        {"source_snapshot_digest": "bad"},
        {"source_sequence": True},
    ),
)
def test_evolution_ledger_entry_rejects_invalid_source_identity(overrides: dict[str, object]) -> None:
    values = {
        "candidate_id": "candidate",
        "base_generation": "g1",
        "adopted_generation": "g2",
        "evaluation_pair_id": "pair",
        "target_spec_digest": "spec",
        "source_snapshot_digest": SOURCE_DIGEST,
        "source_sequence": 1,
    }
    values.update(overrides)
    with pytest.raises(ValueError):
        EvolutionLedgerEntry(**values)  # type: ignore[arg-type]


def test_adoption_base_state_requires_typed_aggregate_values() -> None:
    aggregate = AggregateValue("architecture", 1, "g1", "a" * 64, {})
    with pytest.raises(ValueError, match="typed aggregate"):
        AdoptionBaseState(aggregate, object())  # type: ignore[arg-type]


def test_materialized_candidate_requires_same_generation_identity() -> None:
    with pytest.raises(ValueError, match="identity mismatch"):
        MaterializedCandidate("g3", _prepared(generation="g2"))


@pytest.mark.parametrize(
    "overrides",
    (
        {"prepared_generation": _prepared(generation="other")},
        {"architecture_mutation": _mutation("architecture", generation="other")},
        {"ledger_mutation": _mutation("ledger", generation="other")},
        {"ledger_entry": _entry(generation="other")},
        {"ledger_entry": _entry(candidate_id="other")},
    ),
)
def test_prepared_adoption_rejects_cross_authority_identity_drift(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _adoption(**overrides)


def test_prepared_adoption_accepts_one_consistent_authority_cut() -> None:
    adoption = _adoption()
    assert adoption.generation == "g2"
    assert adoption.prepared_generation.source_snapshot_digest == adoption.ledger_entry.source_snapshot_digest
