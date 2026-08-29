from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from projects.sem_paper.composition.scientific_metrics import (
    DirectoryScientificAuxiliarySampleStore,
    SCIENTIFIC_AUXILIARY_SAMPLE_SCHEMA_VERSION,
    ScientificAuxiliarySampleEvidence,
    ScientificMetricComputationError,
)


def _sample(*, value: float = 0.2) -> ScientificAuxiliarySampleEvidence:
    return ScientificAuxiliarySampleEvidence(
        schema_version=SCIENTIFIC_AUXILIARY_SAMPLE_SCHEMA_VERSION,
        sample_id="sample:Seed-C",
        run_id="run-1",
        seed_id="Seed-C",
        source_tree_digest="a" * 64,
        plan_digest="b" * 64,
        trajectory_divergence=value,
        held_out_causal_effect=0.1,
        held_out_positive_edit_fraction=0.5,
        gate_to_audit_generalization_gap=0.0,
        evidence_refs=("artifact://audit/seed-c",),
    )


def test_scientific_sample_publish_is_idempotent_for_identical_truth(tmp_path) -> None:
    store = DirectoryScientificAuxiliarySampleStore(tmp_path / "samples")
    sample = _sample()
    first = store.publish(sample)
    second = store.publish(sample)
    assert first == second
    assert store.load_all() == (sample,)


def test_scientific_sample_publish_rejects_competing_authority(tmp_path) -> None:
    store = DirectoryScientificAuxiliarySampleStore(tmp_path / "samples")
    store.publish(_sample())
    with pytest.raises(ScientificMetricComputationError, match="authority conflict"):
        store.publish(replace(_sample(), trajectory_divergence=0.9))
    assert store.load_all() == (_sample(),)


def test_concurrent_scientific_sample_publish_never_last_writer_wins(tmp_path) -> None:
    store = DirectoryScientificAuxiliarySampleStore(tmp_path / "samples")
    left = _sample(value=0.2)
    right = replace(_sample(), trajectory_divergence=0.8)
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda sample: _publish(store, sample), (left, right)))
    assert sorted(outcomes) == ["conflict", "published"]
    stored = store.load_all()
    assert len(stored) == 1
    assert stored[0] in {left, right}


def _publish(store, sample) -> str:
    try:
        store.publish(sample)
    except ScientificMetricComputationError:
        return "conflict"
    return "published"
