from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Mapping


class CanonicalEncodingError(TypeError):
    """Value cannot be represented by the platform canonical JSON contract."""


_DEFAULT_MAX_DEPTH = 128
_CONTAINER_TYPES = (Mapping, list, tuple, set, frozenset)


def _enter(value: object, active: set[int], *, depth: int, max_depth: int) -> int | None:
    if depth > max_depth:
        raise CanonicalEncodingError(f"canonical payload exceeds maximum depth {max_depth}")
    recursive = isinstance(value, _CONTAINER_TYPES) or (is_dataclass(value) and not isinstance(value, type))
    if not recursive:
        return None
    identity = id(value)
    if identity in active:
        raise CanonicalEncodingError("cyclic canonical payload is forbidden")
    active.add(identity)
    return identity


def _normalize(value: object, *, active: set[int], depth: int, max_depth: int) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise CanonicalEncodingError("non-finite floats are forbidden in canonical payloads")
        return value
    if isinstance(value, Enum):
        return _normalize(value.value, active=active, depth=depth + 1, max_depth=max_depth)
    if isinstance(value, bytes):
        return {"$bytes_sha256": hashlib.sha256(value).hexdigest(), "$bytes_size": len(value)}
    if isinstance(value, Path):
        # Path stringification is deterministic only when callers already agree on
        # host/path flavor. Cross-machine scientific identities should pass an
        # explicitly normalized portable string rather than a native Path.
        return str(value)

    entered = _enter(value, active, depth=depth, max_depth=max_depth)
    try:
        if is_dataclass(value) and not isinstance(value, type):
            snapshot = tuple(
                (field.name, getattr(value, field.name))
                for field in fields(value)
                if not field.metadata.get("transient", False)
            )
            return {
                name: _normalize(item, active=active, depth=depth + 1, max_depth=max_depth)
                for name, item in snapshot
            }
        if isinstance(value, Mapping):
            snapshot = tuple(value.items())
            rows: dict[str, object] = {}
            for key, item in snapshot:
                if not isinstance(key, str):
                    raise CanonicalEncodingError("canonical mappings require string keys")
                rows[key] = _normalize(item, active=active, depth=depth + 1, max_depth=max_depth)
            return rows
        if isinstance(value, (set, frozenset)):
            snapshot = tuple(value)
            normalized = [
                _normalize(item, active=active, depth=depth + 1, max_depth=max_depth)
                for item in snapshot
            ]
            return sorted(
                normalized,
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            )
        if isinstance(value, (tuple, list)):
            snapshot = tuple(value)
            return [
                _normalize(item, active=active, depth=depth + 1, max_depth=max_depth)
                for item in snapshot
            ]
        raise CanonicalEncodingError(f"unsupported canonical payload type: {type(value).__name__}")
    finally:
        if entered is not None:
            active.remove(entered)


def canonical_bytes(
    value: object,
    *,
    indent: int | None = None,
    max_depth: int = _DEFAULT_MAX_DEPTH,
) -> bytes:
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    kwargs: dict[str, object] = {
        "sort_keys": True,
        "ensure_ascii": False,
        "allow_nan": False,
    }
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    normalized = _normalize(value, active=set(), depth=0, max_depth=max_depth)
    return json.dumps(normalized, **kwargs).encode("utf-8")


def canonical_text(value: object, *, indent: int | None = None, max_depth: int = _DEFAULT_MAX_DEPTH) -> str:
    return canonical_bytes(value, indent=indent, max_depth=max_depth).decode("utf-8")


def canonical_digest(value: object, *, max_depth: int = _DEFAULT_MAX_DEPTH) -> str:
    return hashlib.sha256(canonical_bytes(value, max_depth=max_depth)).hexdigest()


__all__ = ["CanonicalEncodingError", "canonical_bytes", "canonical_digest", "canonical_text"]
