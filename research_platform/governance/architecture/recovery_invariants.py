from __future__ import annotations

from pathlib import Path

from .source_scan import SourceInvariantViolation, imports, violation


def _audit_contract_firewall(root: Path, package: tuple[str, ...]) -> list[SourceInvariantViolation]:
    base = root / "research_platform"
    for segment in package:
        base = base / segment
    rows: list[SourceInvariantViolation] = []
    if not base.exists():
        return rows
    allowed_platform = {
        "research_platform.observability.status.api",
        "research_platform.reliability.recovery.api",
    }
    for path in sorted(base.rglob("*.py")):
        for module, line in imports(path):
            if module.startswith("research_platform") and not any(
                module == allowed or module.startswith(allowed + ".")
                for allowed in allowed_platform
            ):
                rows.append(violation(
                    root,
                    path,
                    "status_recovery_contract_firewall",
                    line,
                    f"{'/'.join(package)} contract imports concrete/higher platform module {module}",
                ))
    return rows


def _audit_recovery_planner_purity(root: Path) -> list[SourceInvariantViolation]:
    path = root / "research_platform" / "reliability" / "diagnostics" / "runtime" / "runtime_recovery.py"
    if not path.exists():
        return []
    forbidden = (
        "research_platform.execution.runtime.manager",
        "research_platform.model.serving",
        "research_platform.runtime.service.runtime",
        "research_platform.runtime.session.runtime",
        "research_platform.reliability.forensics",
        "research_platform.operator",
        "research_platform.platform.composition.runtime_control",
        "research_platform.reliability.effect.runtime",
    )
    rows: list[SourceInvariantViolation] = []
    for module, line in imports(path):
        if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden):
            rows.append(violation(
                root,
                path,
                "runtime_recovery_planner_purity",
                line,
                f"runtime recovery planner imports execution/storage authority {module}; keep planner pure",
            ))
    return rows


def _audit_status_contract_location(root: Path) -> list[SourceInvariantViolation]:
    legacy = root / "research_platform" / "operator" / "status.py"
    if legacy.exists():
        return [violation(
            root,
            legacy,
            "status_contract_authority",
            1,
            "status contracts reintroduced in operator layer; use research_platform.observability.status.api",
        )]
    return []


def audit_recovery_invariants(root: Path) -> list[SourceInvariantViolation]:
    return (
        _audit_contract_firewall(root, ("observability", "status", "api"))
        + _audit_contract_firewall(root, ("reliability", "recovery", "api"))
        + _audit_recovery_planner_purity(root)
        + _audit_status_contract_location(root)
    )


__all__ = ["audit_recovery_invariants"]
