from __future__ import annotations

import hashlib
import json
from typing import Protocol


class StatePayloadCodec(Protocol):
    def encode(self, payload: object) -> bytes: ...
    def decode(self, raw: bytes) -> object: ...


class StrictJsonStatePayloadCodec:
    """Durable-state codec for plain scientific data, never live Python objects."""

    def encode(self, payload: object) -> bytes:
        return json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    def decode(self, raw: bytes) -> object:
        return json.loads(raw.decode("utf-8"))


def payload_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
