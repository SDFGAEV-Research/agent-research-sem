from __future__ import annotations

from research_platform.governance.system_registry.api import system_catalog


def declared_system_graph() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for descriptor in system_catalog():
        if not descriptor.identity.is_system:
            continue
        for target in descriptor.requires:
            rows.append({"source": descriptor.identity.system_id, "target": target, "relation": "requires"})
    return tuple(sorted(rows, key=lambda row: (str(row["source"]), str(row["target"]))))


def declared_subsystem_graph() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for descriptor in system_catalog():
        if descriptor.identity.is_system:
            continue
        rows.append({
            "source": descriptor.parent_key,
            "target": descriptor.identity.key,
            "relation": "contains",
            "package_prefix": descriptor.package_prefix,
            "provides": descriptor.provides,
            "requires": descriptor.requires,
            "authorities": tuple(authority.authority_id for authority in descriptor.authorities),
            "components": descriptor.components,
        })
    return tuple(sorted(rows, key=lambda row: str(row["target"])))


__all__ = ["declared_subsystem_graph", "declared_system_graph"]
