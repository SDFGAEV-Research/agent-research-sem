from __future__ import annotations

from dataclasses import replace

import pytest

from research_platform.data.state.api import AggregateValue, AtomicMutation
from research_platform.platform.kernel import canonical_digest
from projects.sem_paper.method.self_evolving_memory.adoption_mutations import AdoptionMutationCompiler
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


def _mutation(
    aggregate_id: str,
    *,
    generation: str = "g2",
    expected_generation: str = "g1",
    digest: str | None = None,
) -> AtomicMutation:
    payload: object
    if aggregate_id == "architecture":
        prepared = _prepared(generation=generation)
        payload = {
            "target_spec": {},
            "materialized_records": prepared.records,
            "source_sequence": prepared.source_sequence,
            "source_snapshot_digest": prepared.source_snapshot_digest,
        }
    else:
        payload = [_entry(generation=generation).to_document()]
    return AtomicMutation(
        aggregate_id,
        1,
        expected_generation,
        generation,
        canonical_digest(payload) if digest is None else digest,
        payload,
    )


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


def test_evolution_ledger_document_codec_rejects_unknown_fields_and_bool_sequence() -> None:
    unknown = _entry().to_document()
    unknown["unexpected"] = True
    with pytest.raises(ValueError, match="schema mismatch"):
        EvolutionLedgerEntry.from_document(unknown)

    coerced = _entry().to_document()
    coerced["source_sequence"] = True
    with pytest.raises(ValueError, match="source_sequence"):
        EvolutionLedgerEntry.from_document(coerced)


def test_adoption_base_state_rejects_split_authority_generation() -> None:
    architecture = AggregateValue("architecture", 1, "g1", "a" * 64, {})
    ledger = AggregateValue("ledger", 1, "other", "b" * 64, [])
    with pytest.raises(ValueError, match="generations must match"):
        AdoptionBaseState(architecture, ledger)


def test_materialized_candidate_rejects_non_prepared_generation() -> None:
    committed = replace(_prepared(), status=PreparedStatus.COMMITTED)
    with pytest.raises(ValueError, match="requires a PREPARED"):
        MaterializedCandidate("g2", committed)


def test_prepared_adoption_rejects_mutation_base_generation_drift() -> None:
    with pytest.raises(ValueError, match="base generation mismatch"):
        _adoption(architecture_mutation=_mutation("architecture", expected_generation="old"))


def test_prepared_adoption_rejects_unbound_mutation_digest() -> None:
    with pytest.raises(ValueError, match="mutation digest mismatch"):
        _adoption(architecture_mutation=_mutation("architecture", digest="0" * 64))


def test_prepared_adoption_rejects_duplicate_authority_aggregate() -> None:
    ledger = _mutation("ledger")
    duplicate = AtomicMutation(
        "architecture",
        ledger.expected_version,
        ledger.expected_generation,
        ledger.new_generation,
        ledger.new_digest,
        ledger.new_payload,
    )
    with pytest.raises(ValueError, match="aggregate ids must be distinct"):
        _adoption(ledger_mutation=duplicate)


def test_prepared_adoption_rejects_architecture_payload_cut_drift() -> None:
    mutation = _mutation("architecture")
    payload = dict(mutation.new_payload)
    payload["source_sequence"] = 2
    drifted = AtomicMutation(
        mutation.aggregate_id,
        mutation.expected_version,
        mutation.expected_generation,
        mutation.new_generation,
        canonical_digest(payload),
        payload,
    )
    with pytest.raises(ValueError, match="materialization cut"):
        _adoption(architecture_mutation=drifted)


def test_prepared_adoption_rejects_ledger_tail_drift() -> None:
    mutation = _mutation("ledger")
    payload = [_entry(candidate_id="other").to_document()]
    drifted = AtomicMutation(
        mutation.aggregate_id,
        mutation.expected_version,
        mutation.expected_generation,
        mutation.new_generation,
        canonical_digest(payload),
        payload,
    )
    with pytest.raises(ValueError, match="ledger tail"):
        _adoption(ledger_mutation=drifted)


def test_ledger_compiler_rejects_malformed_existing_row() -> None:
    with pytest.raises(ValueError, match="existing evolution ledger row is invalid"):
        AdoptionMutationCompiler._ledger_document(({"candidate_id": "partial"},))
