from __future__ import annotations

import math
from typing import Any, Mapping

from .contracts import MINECRAFT_ACTION_TYPES


class MinecraftActionContractError(ValueError):
    """A Minecraft action cannot satisfy the provider's typed input contract."""

    def __init__(self, action_type: str, code: str, message: str) -> None:
        super().__init__(f"Minecraft action contract failed [{code}] for {action_type}: {message}")
        self.action_type = action_type
        self.code = code


def _error(action_type: str, code: str, message: str) -> MinecraftActionContractError:
    return MinecraftActionContractError(action_type, code, message)


def _number(action_type: str, name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise _error(action_type, "FIELD_TYPE", f"{name} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise _error(action_type, "FIELD_TYPE", f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise _error(action_type, "FIELD_FINITE", f"{name} must be finite")
    return result


def _integer(action_type: str, name: str, value: Any, *, minimum: int, maximum: int) -> int:
    number = _number(action_type, name, value)
    result = int(number)
    if result != number or not minimum <= result <= maximum:
        raise _error(action_type, "FIELD_RANGE", f"{name} must be an integer in [{minimum}, {maximum}]")
    return result


def _text(action_type: str, name: str, value: Any, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(action_type, "FIELD_TEXT", f"{name} must be a non-empty string")
    result = value.strip()
    if len(result) > maximum:
        raise _error(action_type, "FIELD_LENGTH", f"{name} must be at most {maximum} characters")
    return result


def _position(action_type: str, value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != {"x", "y", "z"}:
        raise _error(action_type, "POSITION_SHAPE", "position must contain exactly x, y and z")
    return {axis: _number(action_type, f"position.{axis}", value[axis]) for axis in ("x", "y", "z")}


def _allowed(action_type: str, payload: Mapping[str, Any], names: set[str]) -> dict[str, Any]:
    unknown = set(payload) - names
    if unknown:
        raise _error(action_type, "UNKNOWN_FIELD", f"unexpected fields: {sorted(str(value) for value in unknown)}")
    return dict(payload)


def validate_minecraft_action(action_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one MC action before it crosses the provider seam.

    The function is independent of Mineflayer, LLM prompting and task
    semantics. Defaults mirror the provider's bounded defaults, while all
    caller-supplied values are checked before any external effect is attempted.
    """

    if action_type not in MINECRAFT_ACTION_TYPES:
        raise _error(action_type, "UNSUPPORTED_ACTION", "action type is not registered")
    if not isinstance(payload, Mapping):
        raise _error(action_type, "PAYLOAD_TYPE", "payload must be a mapping")

    if action_type == "goto":
        value = _allowed(action_type, payload, {"position", "radius"})
        if "position" not in value:
            raise _error(action_type, "MISSING_FIELD", "position is required")
        result = {"position": _position(action_type, value["position"])}
        result["radius"] = _number(action_type, "radius", value.get("radius", 1.5))
        if not 0.1 <= result["radius"] <= 64:
            raise _error(action_type, "FIELD_RANGE", "radius must be in [0.1, 64]")
        return result

    if action_type == "collect_block":
        value = _allowed(action_type, payload, {"block", "query", "count", "max_distance"})
        name = value.get("block", value.get("query"))
        result = {"block": _text(action_type, "block", name)}
        result["count"] = _integer(action_type, "count", value.get("count", 1), minimum=1, maximum=64)
        result["max_distance"] = _number(action_type, "max_distance", value.get("max_distance", 48))
        if not 4 <= result["max_distance"] <= 128:
            raise _error(action_type, "FIELD_RANGE", "max_distance must be in [4, 128]")
        return result

    if action_type == "craft_item":
        value = _allowed(action_type, payload, {"item", "count"})
        result = {"item": _text(action_type, "item", value.get("item"))}
        result["count"] = _integer(action_type, "count", value.get("count", 1), minimum=1, maximum=64)
        return result

    if action_type == "place_block":
        value = _allowed(action_type, payload, {"item", "position"})
        result = {"item": _text(action_type, "item", value.get("item"))}
        if value.get("position") is not None:
            result["position"] = _position(action_type, value["position"])
        return result

    if action_type == "attack_nearest":
        value = _allowed(action_type, payload, {"entity", "query", "max_distance", "max_hits"})
        name = value.get("entity", value.get("query", ""))
        result = {"entity": _text(action_type, "entity", name)}
        result["max_distance"] = _number(action_type, "max_distance", value.get("max_distance", 32))
        if not 1 <= result["max_distance"] <= 128:
            raise _error(action_type, "FIELD_RANGE", "max_distance must be in [1, 128]")
        result["max_hits"] = _integer(action_type, "max_hits", value.get("max_hits", 8), minimum=1, maximum=20)
        return result

    if action_type == "wait":
        value = _allowed(action_type, payload, {"ms"})
        return {"ms": _integer(action_type, "ms", value.get("ms", 500), minimum=0, maximum=10000)}

    if action_type == "chat":
        value = _allowed(action_type, payload, {"message"})
        return {"message": _text(action_type, "message", value.get("message"))}

    if action_type == "observe_entities":
        value = _allowed(action_type, payload, {"max_distance", "limit"})
        result = {"max_distance": _number(action_type, "max_distance", value.get("max_distance", 16))}
        if not 1 <= result["max_distance"] <= 128:
            raise _error(action_type, "FIELD_RANGE", "max_distance must be in [1, 128]")
        result["limit"] = _integer(action_type, "limit", value.get("limit", 32), minimum=1, maximum=100)
        return result

    value = _allowed(action_type, payload, {"query", "limit"})
    result = {"query": _text(action_type, "query", value.get("query"))}
    result["limit"] = _integer(action_type, "limit", value.get("limit", 20), minimum=1, maximum=100)
    return result


__all__ = ["MinecraftActionContractError", "validate_minecraft_action"]
