from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pytest

from research_platform.platform.kernel.canonical import (
    CanonicalEncodingError,
    canonical_digest,
    canonical_text,
)


class Kind(Enum):
    A = "a"


@dataclass
class Payload:
    name: str
    hidden: str = field(default="ignored", metadata={"transient": True})


def test_canonicalization_is_deterministic_for_supported_values() -> None:
    left = {"set": {3, 1, 2}, "tuple": (Kind.A, b"abc"), "record": Payload("x")}
    right = {"record": Payload("x"), "tuple": (Kind.A, b"abc"), "set": {2, 3, 1}}
    assert canonical_text(left) == canonical_text(right)
    assert canonical_digest(left) == canonical_digest(right)


def test_canonicalization_rejects_non_finite_float_and_non_string_keys() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalEncodingError):
            canonical_text(value)
    with pytest.raises(CanonicalEncodingError, match="string keys"):
        canonical_text({1: "x"})


def test_canonicalization_rejects_cycles_with_typed_error() -> None:
    cycle: list[object] = []
    cycle.append(cycle)
    with pytest.raises(CanonicalEncodingError, match="cyclic"):
        canonical_text(cycle)


def test_canonicalization_enforces_explicit_depth_bound() -> None:
    value: object = "leaf"
    for _ in range(8):
        value = [value]
    with pytest.raises(CanonicalEncodingError, match="maximum depth"):
        canonical_text(value, max_depth=4)


def test_canonicalization_rejects_custom_objects() -> None:
    class Custom:
        pass

    with pytest.raises(CanonicalEncodingError, match="unsupported"):
        canonical_text(Custom())


def test_native_path_contract_is_not_claimed_portable() -> None:
    path = Path("root") / "child"
    assert canonical_text(path) == canonical_text(str(path))
