from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping


class DataCanonicalEncodingError(TypeError):
    pass


class DataCanonicalDecodingError(ValueError):
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


def _reject_constant(token: str) -> object:
    raise DataCanonicalDecodingError(
        f"data canonical JSON forbids non-finite constant: {token}"
    )


def _object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DataCanonicalDecodingError(
                f"data canonical JSON contains duplicate object key: {key!r}"
            )
        result[key] = value
    return result


def strict_json_loads(raw: str | bytes) -> object:
    try:
        return json.loads(
            raw,
            parse_constant=_reject_constant,
            object_pairs_hook=_object_from_pairs,
        )
    except DataCanonicalDecodingError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DataCanonicalDecodingError("data canonical JSON cannot be decoded") from exc


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
    "DataCanonicalDecodingError",
    "DataCanonicalEncodingError",
    "canonical_bytes",
    "canonical_digest",
    "canonical_text",
    "strict_json_loads",
]
