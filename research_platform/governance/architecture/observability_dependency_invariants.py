from __future__ import annotations

from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation


def audit_observability_dependency_invariants(root: Path) -> list[SourceInvariantViolation]:
    api = root / "research_platform" / "observability" / "api"
    if not api.exists():
        return []
    rows: list[SourceInvariantViolation] = []
    forbidden = (
        "research_platform.reliability.forensics", "research_platform.observability.telemetry",
        "research_platform.operator", "research_platform.platform.composition.runtime_control",
    )
    for path in sorted(api.rglob("*.py")):
        for module, line in imports(path):
            if module.startswith(forbidden):
                rows.append(violation(root, path, "observability_api_backend_firewall", line, f"observability API imports concrete backend/control-plane module {module}"))
    return rows


__all__ = ["audit_observability_dependency_invariants"]
