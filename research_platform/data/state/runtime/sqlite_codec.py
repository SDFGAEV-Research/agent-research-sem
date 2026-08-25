from __future__ import annotations

import hashlib
import json
from typing import Protocol

from research_platform.platform.kernel import JsonValue


class StatePayloadCodec(Protocol):
    def encode(self, payload: JsonValue) -> bytes: ...
    def decode(self, raw: bytes) -> JsonValue: ...


class StrictJsonStatePayloadCodec:
    """Durable-state codec for plain scientific data, never live Python objects."""

    def encode(self, payload: JsonValue) -> bytes:
        return json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    def decode(self, raw: bytes) -> JsonValue:
        return json.loads(raw.decode("utf-8"))


def payload_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
