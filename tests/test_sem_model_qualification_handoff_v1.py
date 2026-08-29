from __future__ import annotations

from dataclasses import dataclass

import pytest

from projects.sem_paper.composition.model_qualification import (
    SemPaperModelQualificationError,
    platform_canary_provenance_contract_ready,
    qualified_binding_canary_evidence_digests,
)


@dataclass(frozen=True)
class _CanaryBinding:
    runtime_canary_evidence_digests: tuple[str, ...]


def test_current_platform_provenance_handoff_is_ready() -> None:
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
