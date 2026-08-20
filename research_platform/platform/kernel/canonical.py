from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Mapping


class CanonicalEncodingError(TypeError):
    pass


def _normalize(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise CanonicalEncodingError("non-finite floats are forbidden in canonical operation payloads")
        return value
    if isinstance(value, Enum):
        return _normalize(value.value)
    if isinstance(value, bytes):
        return {"$bytes_sha256": hashlib.sha256(value).hexdigest(), "$bytes_size": len(value)}
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _normalize(getattr(value, field.name))
            for field in fields(value)
            if not field.metadata.get("transient", False)
        }
    if isinstance(value, Mapping):
        rows: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalEncodingError("canonical mappings require string keys")
            rows[key] = _normalize(item)
        return rows
    if isinstance(value, (tuple, list)):
        return [_normalize(item) for item in value]
    raise CanonicalEncodingError(f"unsupported canonical operation payload type: {type(value).__name__}")


def canonical_bytes(value: object, *, indent: int | None = None) -> bytes:
    kwargs: dict[str, object] = {
        "sort_keys": True,
        "ensure_ascii": False,
        "allow_nan": False,
    }
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    return json.dumps(_normalize(value), **kwargs).encode("utf-8")


def canonical_text(value: object, *, indent: int | None = None) -> str:
    return canonical_bytes(value, indent=indent).decode("utf-8")


def canonical_digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
