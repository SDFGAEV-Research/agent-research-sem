from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping

from research_platform.platform.kernel import canonical_digest

from ..api import MinecraftObservationEvent


def _position(value: object) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    if not all(key in value for key in ("x", "y", "z")):
        return None
    if any(isinstance(value[key], bool) for key in ("x", "y", "z")):
        return None
    try:
        position = {key: float(value[key]) for key in ("x", "y", "z")}
    except (TypeError, ValueError):
        return None
    return position if all(math.isfinite(item) for item in position.values()) else None


@dataclass(slots=True)
class MinecraftStateProjection:
    """Deterministic read model reduced from grounded bridge observations.

    This is a Minecraft environment projection, not a memory store. It keeps
    only the latest bounded world-facing state needed by an environment
    session, while preserving action verification and death observations for
    reconciliation diagnostics.
    """

    max_entities: int = 256
    username: str = ""
    position: dict[str, float] | None = None
    health: float | None = None
    food: float | None = None
    dimension: str | None = None
    inventory: dict[str, int] = field(default_factory=dict)
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    anchors: dict[str, dict[str, float]] = field(default_factory=dict)
    deaths: int = 0
    last_action_verified: bool | None = None
    last_action: Mapping[str, Any] | None = None
    last_outcome: Mapping[str, Any] | str | None = None
    last_event_sequence: int = 0

    def __post_init__(self) -> None:
        if self.max_entities < 1:
            raise ValueError("Minecraft state max_entities must be positive")

    def ingest(self, event: MinecraftObservationEvent) -> None:
        if event.sequence and event.sequence < self.last_event_sequence:
            raise ValueError(
                "Minecraft bridge event sequence regressed: "
                f"{event.sequence} < {self.last_event_sequence}"
            )
        self.last_event_sequence = max(self.last_event_sequence, event.sequence)
        payload = dict(event.payload)

        if event.kind in {"spawn_snapshot", "self_snapshot"}:
            self._ingest_self_snapshot(payload)
        elif event.kind == "health":
            if payload.get("health") is not None:
                self.health = float(payload["health"])
            if payload.get("food") is not None:
                self.food = float(payload["food"])
        elif event.kind == "entity_observation":
            self._ingest_entity(payload)
        elif event.kind == "death":
            self.deaths += 1
        elif event.kind == "action_result":
            self.last_action_verified = bool(payload.get("verified", False))
            action = payload.get("action")
            self.last_action = dict(action) if isinstance(action, Mapping) else None
            outcome = payload.get("outcome")
            self.last_outcome = dict(outcome) if isinstance(outcome, Mapping) else outcome

    def _ingest_self_snapshot(self, payload: Mapping[str, Any]) -> None:
        self.username = str(payload.get("username") or self.username)
        position = _position(payload.get("position"))
        if position is not None:
            self.position = position
            self.anchors.setdefault("spawn", dict(position))
        if payload.get("health") is not None:
            self.health = float(payload["health"])
        if payload.get("food") is not None:
            self.food = float(payload["food"])
        if payload.get("dimension") is not None:
            self.dimension = str(payload["dimension"])

        inventory: dict[str, int] = {}
        for item in payload.get("inventory", ()) or ():
            if not isinstance(item, Mapping) or not item.get("name"):
                continue
            name = str(item["name"])
            inventory[name] = inventory.get(name, 0) + int(item.get("count", 0))
        self.inventory = inventory

    def _ingest_entity(self, payload: Mapping[str, Any]) -> None:
        entity_id = str(
            payload.get("uuid")
            or payload.get("id")
            or payload.get("username")
            or payload.get("name")
            or ""
        )
        if not entity_id:
            return
        self.entities[entity_id] = dict(payload)
        while len(self.entities) > self.max_entities:
            self.entities.pop(next(iter(self.entities)))

    def replace_entities(self) -> None:
        """Start a fresh entity-observation generation.

        Entity observations are a bounded current-state projection.  Keeping
        rows from a previous scan makes absence indistinguishable from
        presence and contaminates task-level success predicates.
        """

        self.entities.clear()

    def anchor(self, name: str) -> dict[str, float] | None:
        value = self.anchors.get(name)
        return dict(value) if value else None

    def set_anchor(self, name: str, position: Mapping[str, Any] | None = None) -> None:
        if not name.strip():
            raise ValueError("Minecraft anchor name must be non-empty")
        resolved = _position(position) if position is not None else self.position
        if resolved is not None:
            self.anchors[name] = resolved

    def compact(self) -> dict[str, Any]:
        entities = []
        for entity_id, value in sorted(self.entities.items()):
            entities.append(
                {
                    "id": entity_id,
                    "name": value.get("name"),
                    "mob_type": value.get("mob_type"),
                    "type": value.get("type"),
                    "position": value.get("position"),
                    "distance": value.get("distance"),
                }
            )
        return {
            "username": self.username,
            "position": dict(self.position) if self.position else None,
            "health": self.health,
            "food": self.food,
            "dimension": self.dimension,
            "inventory": dict(sorted(self.inventory.items())),
            "nearby_entities": entities,
            "anchors": {
                key: dict(value) for key, value in sorted(self.anchors.items())
            },
            "deaths": self.deaths,
            "last_action_verified": self.last_action_verified,
            "last_action": dict(self.last_action) if self.last_action else None,
            "last_outcome": (
                dict(self.last_outcome)
                if isinstance(self.last_outcome, Mapping)
                else self.last_outcome
            ),
            "last_event_sequence": self.last_event_sequence,
        }

    @classmethod
    def from_compact(
        cls,
        document: Mapping[str, Any],
        *,
        max_entities: int,
    ) -> "MinecraftStateProjection":
        """Validate and rebuild an exact compact projection before live restore."""

        expected = {
            "username",
            "position",
            "health",
            "food",
            "dimension",
            "inventory",
            "nearby_entities",
            "anchors",
            "deaths",
            "last_action_verified",
            "last_action",
            "last_outcome",
            "last_event_sequence",
        }
        if set(document) != expected:
            raise ValueError(
                "Minecraft state checkpoint schema mismatch: "
                f"missing={sorted(expected - set(document))!r} "
                f"unknown={sorted(set(document) - expected)!r}"
            )
        position = None if document["position"] is None else _position(document["position"])
        if document["position"] is not None and position is None:
            raise ValueError("Minecraft state checkpoint position is invalid")
        if isinstance(document["health"], bool) or isinstance(document["food"], bool):
            raise ValueError("Minecraft state checkpoint health/food is invalid")
        health = None if document["health"] is None else float(document["health"])
        food = None if document["food"] is None else float(document["food"])
        if any(value is not None and not math.isfinite(value) for value in (health, food)):
            raise ValueError("Minecraft state checkpoint health/food is non-finite")
        inventory_raw = document["inventory"]
        if not isinstance(inventory_raw, Mapping):
            raise ValueError("Minecraft state checkpoint inventory is invalid")
        inventory: dict[str, int] = {}
        for name, count in inventory_raw.items():
            if (
                not isinstance(name, str)
                or not name.strip()
                or isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
            ):
                raise ValueError("Minecraft state checkpoint inventory row is invalid")
            inventory[name] = count
        anchors_raw = document["anchors"]
        if not isinstance(anchors_raw, Mapping):
            raise ValueError("Minecraft state checkpoint anchors are invalid")
        anchors: dict[str, dict[str, float]] = {}
        for name, value in anchors_raw.items():
            parsed = _position(value)
            if not isinstance(name, str) or not name.strip() or parsed is None:
                raise ValueError("Minecraft state checkpoint anchor row is invalid")
            anchors[name] = parsed
        entities_raw = document["nearby_entities"]
        if not isinstance(entities_raw, list) or len(entities_raw) > max_entities:
            raise ValueError("Minecraft state checkpoint entity rows are invalid")
        entities: dict[str, dict[str, Any]] = {}
        for row in entities_raw:
            if not isinstance(row, Mapping):
                raise ValueError("Minecraft state checkpoint entity row is invalid")
            entity_id = str(row.get("id", ""))
            if not entity_id.strip() or entity_id in entities:
                raise ValueError("Minecraft state checkpoint entity identity is invalid")
            entity = dict(row)
            entity.pop("id", None)
            entity_position = entity.get("position")
            if entity_position is not None:
                parsed_position = _position(entity_position)
                if parsed_position is None:
                    raise ValueError("Minecraft state checkpoint entity position is invalid")
                entity["position"] = parsed_position
            distance = entity.get("distance")
            if distance is not None and (
                isinstance(distance, bool)
                or not isinstance(distance, (int, float))
                or not math.isfinite(float(distance))
            ):
                raise ValueError("Minecraft state checkpoint entity distance is invalid")
            entities[entity_id] = entity
        deaths = document["deaths"]
        last_sequence = document["last_event_sequence"]
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (deaths, last_sequence)
        ):
            raise ValueError("Minecraft state checkpoint counters are invalid")
        last_verified = document["last_action_verified"]
        if last_verified is not None and not isinstance(last_verified, bool):
            raise ValueError("Minecraft state checkpoint action verification is invalid")
        last_action = document["last_action"]
        if last_action is not None and not isinstance(last_action, Mapping):
            raise ValueError("Minecraft state checkpoint last action is invalid")
        last_outcome = document["last_outcome"]
        if last_outcome is not None and not isinstance(last_outcome, (Mapping, str)):
            raise ValueError("Minecraft state checkpoint last outcome is invalid")
        username = document["username"]
        dimension = document["dimension"]
        if not isinstance(username, str) or (
            dimension is not None and not isinstance(dimension, str)
        ):
            raise ValueError("Minecraft state checkpoint text fields are invalid")
        return cls(
            max_entities=max_entities,
            username=username,
            position=position,
            health=health,
            food=food,
            dimension=dimension,
            inventory=inventory,
            entities=entities,
            anchors=anchors,
            deaths=deaths,
            last_action_verified=last_verified,
            last_action=None if last_action is None else dict(last_action),
            last_outcome=(
                dict(last_outcome) if isinstance(last_outcome, Mapping) else last_outcome
            ),
            last_event_sequence=last_sequence,
        )

    def snapshot_digest(self) -> str:
        return canonical_digest(self.compact())


__all__ = ["MinecraftStateProjection"]
