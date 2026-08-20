from __future__ import annotations

from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind


class ScopeRegistryConflict(RuntimeError):
    pass


class ScopeNotRegistered(KeyError):
    pass


class InMemoryScopeRegistry:
    """Single parent-relation authority for all organizational/runtime scopes."""

    def __init__(self) -> None:
        self._parents: dict[ScopeIdentity, ScopeIdentity | None] = {PLATFORM_SCOPE: None}

    def register(self, scope: ScopeIdentity, parent: ScopeIdentity | None) -> None:
        if scope.kind is ScopeKind.PLATFORM:
            if scope != PLATFORM_SCOPE or parent is not None:
                raise ScopeRegistryConflict("platform scope has one fixed root identity")
        elif parent is None:
            raise ScopeRegistryConflict("non-platform scope requires explicit parent")
        elif parent not in self._parents:
            raise ScopeNotRegistered(parent.key)
        current = self._parents.get(scope)
        if scope in self._parents and current != parent:
            raise ScopeRegistryConflict(f"scope parent already fixed: {scope.key}")
        self._parents[scope] = parent

    def parent(self, scope: ScopeIdentity) -> ScopeIdentity | None:
        try:
            return self._parents[scope]
        except KeyError as exc:
            raise ScopeNotRegistered(scope.key) from exc

    def ancestry(self, scope: ScopeIdentity) -> tuple[ScopeIdentity, ...]:
        chain: list[ScopeIdentity] = []
        seen: set[ScopeIdentity] = set()
        current: ScopeIdentity | None = scope
        while current is not None:
            if current in seen:
                raise ScopeRegistryConflict(f"scope cycle detected at {current.key}")
            seen.add(current)
            chain.append(current)
            current = self.parent(current)
        return tuple(chain)

    def children(self, scope: ScopeIdentity) -> tuple[ScopeIdentity, ...]:
        if scope not in self._parents:
            raise ScopeNotRegistered(scope.key)
        return tuple(sorted((item for item, parent in self._parents.items() if parent == scope), key=lambda item: item.key))

    def contains(self, scope: ScopeIdentity) -> bool:
        return scope in self._parents


__all__ = ["InMemoryScopeRegistry", "ScopeNotRegistered", "ScopeRegistryConflict"]
