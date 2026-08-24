from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from ..api.contracts import MinecraftJsonValue


@dataclass(frozen=True, slots=True)
class MinecraftEntityMatch:
    entity: Mapping[str, MinecraftJsonValue]
    distance: float


class MinecraftWorldQuery:
    """Pure queries over the rich observation; never calls the server."""

    @staticmethod
    def inventory_count(state: Mapping[str, MinecraftJsonValue], item: str) -> int:
        inventory = state.get("inventory")
        if not isinstance(inventory, Mapping):
            return 0
        return sum(int(value) for key, value in inventory.items() if item.lower() in str(key).lower())

    @staticmethod
    def nearest_entity(state: Mapping[str, MinecraftJsonValue], query: str = "") -> MinecraftEntityMatch | None:
        entities = state.get("nearby_entities")
        position = state.get("position")
        if not isinstance(entities, (list, tuple)) or not isinstance(position, Mapping):
            return None
        matches: list[MinecraftEntityMatch] = []
        for entity in entities:
            if not isinstance(entity, Mapping):
                continue
            haystack = " ".join(str(entity.get(key, "")) for key in ("name", "type", "mob_type", "username")).lower()
            if query and query.lower() not in haystack:
                continue
            entity_position = entity.get("position")
            if not isinstance(entity_position, Mapping):
                continue
            try:
                distance = math.sqrt(sum((float(position[axis]) - float(entity_position[axis])) ** 2 for axis in ("x", "y", "z")))
            except (KeyError, TypeError, ValueError):
                continue
            matches.append(MinecraftEntityMatch(entity, distance))
        return min(matches, key=lambda match: match.distance) if matches else None

    @staticmethod
    def blocks_matching(state: Mapping[str, MinecraftJsonValue], query: str, *, limit: int = 32) -> tuple[Mapping[str, MinecraftJsonValue], ...]:
        if limit < 1:
            raise ValueError("world block query limit must be positive")
        blocks = state.get("nearby_blocks")
        if not isinstance(blocks, (list, tuple)):
            return ()
        return tuple(block for block in blocks if isinstance(block, Mapping) and query.lower() in str(block.get("name", block.get("block", ""))).lower())[:limit]

    @staticmethod
    def is_safe(state: Mapping[str, MinecraftJsonValue], *, minimum_health: float = 6.0) -> bool:
        try:
            health = float(state.get("health", 0))
        except (TypeError, ValueError):
            return False
        hostiles = state.get("hostile_entities", ())
        return health >= minimum_health and not bool(hostiles)

    @staticmethod
    def resource_summary(state: Mapping[str, MinecraftJsonValue], items: tuple[str, ...]) -> Mapping[str, int]:
        return {item: MinecraftWorldQuery.inventory_count(state, item) for item in items}


@dataclass(frozen=True, slots=True)
class MinecraftRoutine:
    routine_id: str
    objective: str
    min_time: int
    max_time: int
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.routine_id.strip() or not self.objective.strip() or not 0 <= self.min_time <= self.max_time <= 24000:
            raise ValueError("Minecraft routine time window is invalid")


class MinecraftRoutineController:
    """Selects persistent day/night NPC-style objectives from world time."""

    def __init__(self, routines: tuple[MinecraftRoutine, ...]) -> None:
        if not routines:
            raise ValueError("Minecraft routine controller requires routines")
        if len({routine.routine_id for routine in routines}) != len(routines):
            raise ValueError("Minecraft routine ids must be unique")
        self._routines = routines

    def active(self, state: Mapping[str, MinecraftJsonValue]) -> MinecraftRoutine | None:
        try:
            time_of_day = int(state.get("time_of_day", state.get("time", 0))) % 24000
        except (TypeError, ValueError):
            return None
        selected = [routine for routine in self._routines if routine.min_time <= time_of_day <= routine.max_time]
        return max(selected, key=lambda routine: (routine.priority, routine.routine_id)) if selected else None


__all__ = ["MinecraftEntityMatch", "MinecraftRoutine", "MinecraftRoutineController", "MinecraftWorldQuery"]
