from __future__ import annotations

from research_platform.governance.system_registry.api import SystemDescriptor


class SystemRegistryConflict(RuntimeError):
    pass


class SystemRegistryNotFound(KeyError):
    pass


class InMemorySystemRegistry:
    """Recursive system-tree authority. It owns topology, not system behavior."""

    def __init__(self) -> None:
        self._items: dict[str, SystemDescriptor] = {}

    def register(self, descriptor: SystemDescriptor) -> None:
        key = descriptor.identity.key
        current = self._items.get(key)
        if current is not None:
            if current != descriptor:
                raise SystemRegistryConflict(key)
            return

        parent = descriptor.parent_key
        if parent is not None and parent not in self._items:
            raise SystemRegistryNotFound(parent)

        self._items[key] = descriptor

    def contains(self, key: str) -> bool:
        return key in self._items

    def get(self, key: str) -> SystemDescriptor:
        try:
            return self._items[key]
        except KeyError as exc:
            raise SystemRegistryNotFound(key) from exc

    def list(self) -> tuple[SystemDescriptor, ...]:
        return tuple(self._items[k] for k in sorted(self._items))

    def children(self, key: str) -> tuple[SystemDescriptor, ...]:
        self.get(key)
        return tuple(row for row in self.list() if row.parent_key == key)

    def descendants(self, key: str) -> tuple[SystemDescriptor, ...]:
        self.get(key)
        result: list[SystemDescriptor] = []
        frontier = [key]
        while frontier:
            parent = frontier.pop(0)
            children = self.children(parent)
            result.extend(children)
            frontier.extend(item.identity.key for item in children)
        return tuple(result)

    def ancestors(self, key: str) -> tuple[SystemDescriptor, ...]:
        current = self.get(key)
        result: list[SystemDescriptor] = []
        while current.parent_key is not None:
            current = self.get(current.parent_key)
            result.append(current)
        return tuple(result)

    def owner_for_module(self, module: str) -> SystemDescriptor | None:
        candidates = [
            row
            for row in self._items.values()
            if module == row.package_prefix or module.startswith(row.package_prefix + ".")
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: len(row.package_prefix))


__all__ = ["InMemorySystemRegistry", "SystemRegistryConflict", "SystemRegistryNotFound"]
