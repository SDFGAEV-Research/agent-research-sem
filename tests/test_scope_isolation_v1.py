from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind
from research_platform.scope.providers import SQLiteScopeRegistry
from research_platform.scope.runtime import InMemoryScopeRegistry


def _register_many_children(registry, *, count: int = 64) -> tuple[ScopeIdentity, ...]:
    workspace = ScopeIdentity(ScopeKind.WORKSPACE, "ws")
    registry.register(workspace, PLATFORM_SCOPE)
    children = tuple(ScopeIdentity(ScopeKind.PROGRAM, f"program-{index:03d}") for index in range(count))
    with ThreadPoolExecutor(max_workers=8) as pool:
        tuple(pool.map(lambda child: registry.register(child, workspace), children))
    return children


def test_in_memory_scope_registry_is_thread_safe_for_concurrent_children() -> None:
    registry = InMemoryScopeRegistry()
    children = _register_many_children(registry)
    workspace = ScopeIdentity(ScopeKind.WORKSPACE, "ws")
    assert registry.children(workspace) == tuple(sorted(children, key=lambda item: item.key))


def test_sqlite_scope_registry_is_thread_safe_for_concurrent_children() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "scope.sqlite"
        registry = SQLiteScopeRegistry(path, timeout_seconds=5.0)
        children = _register_many_children(registry)
        workspace = ScopeIdentity(ScopeKind.WORKSPACE, "ws")
        assert registry.children(workspace) == tuple(sorted(children, key=lambda item: item.key))
        assert SQLiteScopeRegistry(path).children(workspace) == tuple(sorted(children, key=lambda item: item.key))
