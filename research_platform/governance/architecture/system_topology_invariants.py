from __future__ import annotations

from pathlib import Path

from research_platform.governance.system_registry.api import system_catalog
from research_platform.governance.system_registry.api.contracts import STANDARD_SYSTEM_SHAPE

from .source_scan import SourceInvariantViolation, violation


def _standard_shape_packages(root: Path) -> tuple[tuple[Path, str], ...]:
    package_root = root / "research_platform"
    rows: list[tuple[Path, str]] = []
    for path in sorted(package_root.rglob("*")):
        if not path.is_dir() or not (path / "__init__.py").is_file():
            continue
        relative = path.relative_to(package_root)
        # api/runtime/providers/composition are implementation planes, not systems.
        if any(part in STANDARD_SYSTEM_SHAPE for part in relative.parts):
            continue
        if not all(
            (path / plane).is_dir() and (path / plane / "__init__.py").is_file()
            for plane in STANDARD_SYSTEM_SHAPE
        ):
            continue
        module = "research_platform." + ".".join(relative.parts)
        rows.append((path, module))
    return tuple(rows)


def audit_system_topology_completeness(root: Path) -> list[SourceInvariantViolation]:
    """Fail closed when a concrete standard-shaped system lacks catalog ownership.

    The catalog remains the sole topology declaration authority. Filesystem shape is
    only discovery evidence: it can prove that a system implementation exists and
    therefore must have an explicit catalog owner, but it never creates topology by
    inference.
    """

    root = Path(root).resolve()
    registered = {row.package_prefix for row in system_catalog()}
    rows: list[SourceInvariantViolation] = []
    for path, module in _standard_shape_packages(root):
        if module in registered:
            continue
        rows.append(violation(
            root,
            path / "__init__.py",
            "unregistered_standard_system",
            1,
            (
                f"standard system shape exists at {module} but no canonical "
                "system_registry/catalog.json descriptor owns it"
            ),
        ))
    return rows


__all__ = ["audit_system_topology_completeness"]
