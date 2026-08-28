from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping


class ArtifactCanonicalEncodingError(TypeError):
    pass


def _normalize(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ArtifactCanonicalEncodingError("artifact canonical JSON forbids non-finite floats")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ArtifactCanonicalEncodingError("artifact canonical mappings require string keys")
            normalized[key] = _normalize(item)
        return normalized
    if isinstance(value, (tuple, list)):
        return [_normalize(item) for item in value]
    raise ArtifactCanonicalEncodingError(
        f"unsupported artifact canonical value: {type(value).__name__}"
    )


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


__all__ = [
    "ArtifactCanonicalEncodingError",
    "canonical_bytes",
    "canonical_digest",
]
