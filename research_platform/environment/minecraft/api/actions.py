from __future__ import annotations

import math
from typing import Any, Mapping

from .contracts import (
    MINECRAFT_ACTION_SPECS,
    MINECRAFT_ACTION_SPEC_BY_TYPE,
    MINECRAFT_ACTION_TYPES,
    MinecraftPlannerActionContract,
)


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


def _distance(
    action_type: str,
    name: str,
    value: Any,
    *,
    default: float,
    minimum: float = 1.0,
    maximum: float = 128.0,
) -> float:
    result = _number(action_type, name, default if value is None else value)
    if not minimum <= result <= maximum:
        raise _error(action_type, "FIELD_RANGE", f"{name} must be in [{minimum}, {maximum}]")
    return result


def _item_count(action_type: str, value: Mapping[str, Any], *, maximum: int = 64) -> dict[str, Any]:
    return {
        "item": _text(action_type, "item", value.get("item")),
        "count": _integer(
            action_type,
            "count",
            value.get("count", 1),
            minimum=1,
            maximum=maximum,
        ),
    }


def minecraft_action_timeout(action_type: str, base_timeout_s: float) -> float:
    """Return the catalog-bound timeout without granting callers arbitrary duration."""

    if base_timeout_s <= 0:
        raise ValueError("Minecraft base action timeout must be positive")
    try:
        spec = MINECRAFT_ACTION_SPEC_BY_TYPE[action_type]
    except KeyError as exc:
        raise _error(action_type, "UNSUPPORTED_ACTION", "action type is not registered") from exc
    return base_timeout_s * spec.timeout_multiplier


def minecraft_action_catalog() -> tuple[MinecraftPlannerActionContract, ...]:
    """Return the exact platform MC tool catalog exposed to planners/providers."""

    return tuple(spec.planner_contract() for spec in MINECRAFT_ACTION_SPECS)


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

    if action_type == "goto_entity":
        value = _allowed(action_type, payload, {"entity", "max_distance", "radius"})
        result = {"entity": _text(action_type, "entity", value.get("entity"))}
        result["max_distance"] = _distance(
            action_type, "max_distance", value.get("max_distance"), default=64
        )
        result["radius"] = _distance(
            action_type, "radius", value.get("radius"), default=2.5, minimum=1, maximum=16
        )
        return result

    if action_type == "move_away":
        value = _allowed(action_type, payload, {"distance"})
        return {
            "distance": _distance(
                action_type, "distance", value.get("distance"), default=8, maximum=64
            )
        }

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
        return _item_count(action_type, value)

    if action_type == "smelt_item":
        value = _allowed(
            action_type,
            payload,
            {"item", "count", "fuel", "max_distance", "max_wait_s"},
        )
        result = _item_count(action_type, value, maximum=8)
        if value.get("fuel") is not None:
            result["fuel"] = _text(action_type, "fuel", value["fuel"])
        result["max_distance"] = _distance(
            action_type, "max_distance", value.get("max_distance"), default=32
        )
        result["max_wait_s"] = _distance(
            action_type, "max_wait_s", value.get("max_wait_s"), default=90, minimum=10, maximum=180
        )
        return result

    if action_type == "clear_furnace":
        value = _allowed(action_type, payload, {"max_distance"})
        return {
            "max_distance": _distance(
                action_type, "max_distance", value.get("max_distance"), default=32
            )
        }

    if action_type == "place_block":
        value = _allowed(action_type, payload, {"item", "position"})
        result = {"item": _text(action_type, "item", value.get("item"))}
        if value.get("position") is not None:
            result["position"] = _position(action_type, value["position"])
        return result

    if action_type == "equip_item":
        value = _allowed(action_type, payload, {"item", "destination"})
        destination = str(value.get("destination", "hand"))
        allowed_destinations = {"hand", "off-hand", "head", "torso", "legs", "feet"}
        if destination not in allowed_destinations:
            raise _error(
                action_type,
                "FIELD_VALUE",
                f"destination must be one of {sorted(allowed_destinations)}",
            )
        return {
            "item": _text(action_type, "item", value.get("item")),
            "destination": destination,
        }

    if action_type == "consume_item":
        value = _allowed(action_type, payload, {"item"})
        return {"item": _text(action_type, "item", value.get("item"))}

    if action_type == "discard_item":
        value = _allowed(action_type, payload, {"item", "count"})
        return _item_count(action_type, value)

    if action_type == "give_item":
        value = _allowed(action_type, payload, {"player", "item", "count"})
        return {
            "player": _text(action_type, "player", value.get("player"), maximum=16),
            **_item_count(action_type, value),
        }

    if action_type in {"chest_deposit", "chest_withdraw"}:
        value = _allowed(action_type, payload, {"item", "count", "max_distance"})
        result = _item_count(action_type, value)
        result["max_distance"] = _distance(
            action_type, "max_distance", value.get("max_distance"), default=32
        )
        return result

    if action_type == "chest_inspect":
        value = _allowed(action_type, payload, {"max_distance"})
        return {
            "max_distance": _distance(
                action_type, "max_distance", value.get("max_distance"), default=32
            )
        }

    if action_type == "attack_nearest":
        value = _allowed(action_type, payload, {"entity", "query", "max_distance", "max_hits"})
        name = value.get("entity", value.get("query", ""))
        result = {"entity": _text(action_type, "entity", name)}
        result["max_distance"] = _number(action_type, "max_distance", value.get("max_distance", 32))
        if not 1 <= result["max_distance"] <= 128:
            raise _error(action_type, "FIELD_RANGE", "max_distance must be in [1, 128]")
        result["max_hits"] = _integer(action_type, "max_hits", value.get("max_hits", 8), minimum=1, maximum=20)
        return result

    if action_type == "attack_entity":
        value = _allowed(action_type, payload, {"entity_id", "max_distance", "max_hits"})
        return {
            "entity_id": _integer(
                action_type, "entity_id", value.get("entity_id"), minimum=0, maximum=2**31 - 1
            ),
            "max_distance": _distance(
                action_type, "max_distance", value.get("max_distance"), default=32
            ),
            "max_hits": _integer(
                action_type, "max_hits", value.get("max_hits", 12), minimum=1, maximum=40
            ),
        }

    if action_type == "attack_player":
        value = _allowed(action_type, payload, {"player", "max_distance", "max_hits"})
        return {
            "player": _text(action_type, "player", value.get("player"), maximum=16),
            "max_distance": _distance(
                action_type, "max_distance", value.get("max_distance"), default=64
            ),
            "max_hits": _integer(
                action_type, "max_hits", value.get("max_hits", 20), minimum=1, maximum=40
            ),
        }

    if action_type == "ranged_attack":
        value = _allowed(
            action_type,
            payload,
            {"entity", "player", "max_distance", "shots", "charge_ms"},
        )
        entity = value.get("player", value.get("entity"))
        result = {
            "entity": _text(action_type, "entity", entity),
            "max_distance": _distance(
                action_type, "max_distance", value.get("max_distance"), default=48
            ),
            "shots": _integer(
                action_type, "shots", value.get("shots", 1), minimum=1, maximum=8
            ),
            "charge_ms": _integer(
                action_type, "charge_ms", value.get("charge_ms", 1100), minimum=100, maximum=2000
            ),
        }
        return result

    if action_type == "defend_self":
        value = _allowed(action_type, payload, {"radius", "max_targets", "max_hits"})
        return {
            "radius": _distance(
                action_type, "radius", value.get("radius"), default=12, maximum=32
            ),
            "max_targets": _integer(
                action_type, "max_targets", value.get("max_targets", 4), minimum=1, maximum=16
            ),
            "max_hits": _integer(
                action_type, "max_hits", value.get("max_hits", 12), minimum=1, maximum=40
            ),
        }

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


__all__ = [
    "MinecraftActionContractError",
    "minecraft_action_catalog",
    "minecraft_action_timeout",
    "validate_minecraft_action",
]
