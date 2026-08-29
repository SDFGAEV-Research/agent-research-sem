from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from projects.sem_paper.composition.model_qualification import (
    SemPaperModelQualificationError,
    platform_canary_provenance_contract_ready,
    qualified_binding_canary_evidence_digests,
    sem_planner_runtime_canary_probe,
    verify_sem_planner_canary_authority,
)


@dataclass(frozen=True)
class _Model:
    model_id: str = "sem-qwen38-27b"


@dataclass(frozen=True)
class _CanaryBinding:
    runtime_canary_evidence_digests: tuple[str, ...]
    model: _Model = field(default_factory=_Model)


@dataclass(frozen=True)
class _Evidence:
    evidence_digest: str
    role: str
    canary_id: str
    suite_digest: str
    probe_digest: str
    contract_digest: str
    passed: bool


@dataclass(frozen=True)
class _Closure:
    runtime_canary_evidence: tuple[_Evidence, ...]


def test_current_platform_provenance_handoff_is_available() -> None:
    assert platform_canary_provenance_contract_ready() is True


def test_binding_canary_identity_is_sorted_and_content_addressed() -> None:
    first = "b" * 64
    second = "a" * 64
    binding = _CanaryBinding((first, second))
    assert qualified_binding_canary_evidence_digests(binding) == (second, first)


def test_binding_without_canary_identity_is_rejected() -> None:
    with pytest.raises(SemPaperModelQualificationError, match="does not carry"):
        qualified_binding_canary_evidence_digests(object())


def test_binding_rejects_invalid_or_duplicate_canary_identity() -> None:
    with pytest.raises(SemPaperModelQualificationError, match="SHA-256"):
        qualified_binding_canary_evidence_digests(_CanaryBinding(("bad",)))
    duplicate = "c" * 64
    with pytest.raises(SemPaperModelQualificationError, match="duplicate"):
        qualified_binding_canary_evidence_digests(_CanaryBinding((duplicate, duplicate)))


def test_exact_sem_planner_probe_authorizes_binding() -> None:
    probe = sem_planner_runtime_canary_probe("sem-qwen38-27b")
    digest = "d" * 64
    evidence = _Evidence(
        digest, "planner", probe.canary_id, probe.suite_digest, probe.digest(),
        probe.contract.digest(), True,
    )
    binding = _CanaryBinding((digest,))
    assert verify_sem_planner_canary_authority(_Closure((evidence,)), binding) == (digest,)


def test_different_probe_cannot_authorize_binding() -> None:
    probe = sem_planner_runtime_canary_probe("sem-qwen38-27b")
    digest = "e" * 64
    evidence = _Evidence(
        digest, "planner", probe.canary_id, probe.suite_digest, "f" * 64,
        probe.contract.digest(), True,
    )
    with pytest.raises(SemPaperModelQualificationError, match="exact SEM non-thinking canary"):
        verify_sem_planner_canary_authority(_Closure((evidence,)), _CanaryBinding((digest,)))
