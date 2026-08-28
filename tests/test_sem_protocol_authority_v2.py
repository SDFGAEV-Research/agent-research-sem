from __future__ import annotations

from dataclasses import replace

import pytest

from projects.sem_paper.composition.study import (
    CORE6_REPETITIONS,
    CORE6_VARIANTS,
    build_sem_paper_confirmatory_protocol,
    build_sem_paper_conformance_protocol,
    build_sem_paper_study_protocol,
    is_confirmatory_protocol,
)


def _inputs() -> dict[str, object]:
    return {
        "study_id": "protocol-authority",
        "workload_id": "protocol-authority-workload",
        "task_manifest_digest": "a" * 64,
        "seed_identity": {"seed": "frozen"},
        "fixed_configuration": {"kind": "fixed"},
        "candidate_configuration": {"kind": "candidate"},
    }


def test_confirmatory_factory_is_exact_frozen_core6() -> None:
    protocol = build_sem_paper_confirmatory_protocol(**_inputs())
    assert protocol.repetitions == CORE6_REPETITIONS
    assert len(protocol.variants) == len(CORE6_VARIANTS) == 6
    assert set(protocol.budget_tiers) == {"core"}
    assert is_confirmatory_protocol(protocol)


def test_core6_repetition_override_fails_closed() -> None:
    with pytest.raises(ValueError, match="repetitions are frozen"):
        build_sem_paper_study_protocol(
            **_inputs(),
            matrix_profile="core-6",
            repetitions=CORE6_REPETITIONS + 1,
        )


def test_confirmatory_predicate_rejects_nonfrozen_repetition_count() -> None:
    protocol = build_sem_paper_confirmatory_protocol(**_inputs())
    assert not is_confirmatory_protocol(
        replace(protocol, repetitions=CORE6_REPETITIONS + 1)
    )


def test_conformance_factory_is_explicitly_nonclaim() -> None:
    protocol = build_sem_paper_conformance_protocol(**_inputs(), repetitions=2)
    assert protocol.repetitions == 2
    assert len(protocol.variants) == 2
    assert set(protocol.budget_tiers) == {"standard"}
    assert not is_confirmatory_protocol(protocol)


def test_seed_schedule_digest_binds_profile_and_repetitions() -> None:
    one = build_sem_paper_conformance_protocol(**_inputs(), repetitions=1)
    two = build_sem_paper_conformance_protocol(**_inputs(), repetitions=2)
    confirmatory = build_sem_paper_confirmatory_protocol(**_inputs())
    assert len({one.seed_schedule_digest, two.seed_schedule_digest, confirmatory.seed_schedule_digest}) == 3
