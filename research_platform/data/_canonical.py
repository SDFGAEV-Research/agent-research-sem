from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping


class DataCanonicalEncodingError(TypeError):
    pass


def _normalize(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DataCanonicalEncodingError("data canonical JSON forbids non-finite floats")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DataCanonicalEncodingError("data canonical mappings require string keys")
            normalized[key] = _normalize(item)
        return normalized
    if isinstance(value, (tuple, list)):
        return [_normalize(item) for item in value]
    raise DataCanonicalEncodingError(
        f"unsupported data canonical value: {type(value).__name__}"
    )


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_text(value: object) -> str:
    return canonical_bytes(value).decode("utf-8")


def canonical_digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


__all__ = [
    "DataCanonicalEncodingError",
    "canonical_bytes",
    "canonical_digest",
    "canonical_text",
]
