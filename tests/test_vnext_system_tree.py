from research_platform.governance.system_registry.api import SystemDescriptor, SystemIdentity, SystemLayer
from research_platform.governance.system_registry.runtime.registry import (
    InMemorySystemRegistry,
    SystemRegistryConflict,
)


def node(key: tuple[str, ...], pkg: str) -> SystemDescriptor:
    return SystemDescriptor(
        identity=SystemIdentity(key[0], key[1:]),
        layer=SystemLayer.KERNEL if len(key) == 1 else SystemLayer.INFRASTRUCTURE,
        package_prefix=pkg,
    )


def test_recursive_system_tree_exposes_explicit_ownership() -> None:
    registry = InMemorySystemRegistry()
    registry.register(node(("kernel",), "research_platform.platform.kernel"))
    registry.register(node(("kernel", "identity"), "research_platform.platform.kernel.identity"))
    registry.register(node(("kernel", "errors"), "research_platform.platform.kernel.errors"))

    assert [x.identity.key for x in registry.children("kernel")] == ["kernel/errors", "kernel/identity"]
    assert [x.identity.key for x in registry.descendants("kernel")] == ["kernel/errors", "kernel/identity"]
    assert registry.ancestors("kernel/errors")[0].identity.key == "kernel"
    assert registry.owner_for_module("research_platform.platform.kernel.errors.descriptor").identity.key == "kernel/errors"


def test_system_child_requires_registered_parent() -> None:
    registry = InMemorySystemRegistry()
    try:
        registry.register(node(("kernel", "errors"), "research_platform.reliability"))
    except Exception as exc:
        assert exc.__class__.__name__ == "SystemRegistryNotFound"
    else:
        raise AssertionError("system tree allowed an unregistered parent")
